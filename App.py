import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io
import yfinance as yf

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Tableau de Bord Stratégique FO", layout="wide", page_icon="🏢")

# --- PARAMÈTRES GLOBAUX ---
TAUX_SANS_RISQUE = 0.04  # 4.00%
RENDEMENT_FPI_CIBLE_DEFAUT = 0.08  # 8.00% par défaut si l'API boursière échoue

# --- MOTEUR BOURSIER EN TEMPS RÉEL (YAHOO FINANCE) ---
@st.cache_data(ttl=86400)  # Met en cache pour 24h
def get_real_index_cagr(ticker="XRE.TO", annees_historique=5):
    try:
        # Télécharge l'historique de l'indice
        historique = yf.Ticker(ticker).history(period=f"{annees_historique}y")
        
        if historique.empty:
            return RENDEMENT_FPI_CIBLE_DEFAUT
            
        prix_initial = historique['Close'].iloc[0]
        prix_final = historique['Close'].iloc[-1]
        
        # Formule du Taux de Croissance Annuel Composé (TCAC)
        tcac = (prix_final / prix_initial) ** (1 / annees_historique) - 1
        return tcac
    except Exception:
        return RENDEMENT_FPI_CIBLE_DEFAUT

# --- GÉNÉRATEUR DE GABARIT (TEMPLATE) ---
@st.cache_data
def get_template_csv():
    # Génère un fichier CSV modèle directement depuis le code
    df_template = pd.DataFrame({
        'ID': ['Immeuble Alpha (MTL)', 'Immeuble Beta (QC)', 'Tour Gamma (IO)'],
        'Valeur_Marchande': [10000000, 12500000, 15000000],
        'Dette': [7000000, 6000000, 8000000],
        'RNE': [350000, 742000, 600000],
        'Taux_Interet': [0.055, 0.048, 0.060],
        'Amortissement_Annees': [25, 20, 0]  # 0 = Interest Only
    })
    return df_template.to_csv(index=False).encode('utf-8')

# --- TRAITEMENT DES DONNÉES EN MÉMOIRE ---
@st.cache_data
def process_data(file, filename):
    # Lecture dynamique selon le type de fichier
    if filename.endswith('.csv'):
        data = pd.read_csv(file)
    else:
        data = pd.read_excel(file)
        
    # --- 1. MOTEUR DE CALCUL DU SERVICE DE LA DETTE ---
    r = data['Taux_Interet'] / 12
    n = data['Amortissement_Annees'] * 12
    
    # Prêts amortis (si Amortissement > 0)
    # Remplacement des valeurs infinies/NaN par 0 temporairement pour le calcul vectorisé
    r_safe = np.where(r == 0, 1e-10, r) 
    paiement_annuel_amorti = (data['Dette'] * (r_safe / (1 - (1 + r_safe)**(-n)))) * 12
    
    # Prêts "Interest Only" (intérêts seuls, si Amortissement = 0)
    paiement_interets_seuls = data['Dette'] * data['Taux_Interet']
    
    # Application de la bonne formule
    data['Service_Dette'] = np.where(data['Amortissement_Annees'] > 0, paiement_annuel_amorti, paiement_interets_seuls)
    
    # --- 2. CALCULS DES MÉTRIQUES DE PERFORMANCE ---
    data['Equite_Nette'] = data['Valeur_Marchande'] - data['Dette']
    data['RCSD'] = data['RNE'] / data['Service_Dette']
    data['ROE'] = (data['RNE'] - data['Service_Dette']) / data['Equite_Nette']
    
    # --- 3. TRIGGERS (DÉFINITION DU STATUT) ---
    conditions = [
        (data['RCSD'] < 1.0) | (data['ROE'] < TAUX_SANS_RISQUE),
        (data['RCSD'] >= 1.0) & (data['RCSD'] <= 1.25) & (data['ROE'] >= TAUX_SANS_RISQUE),
        (data['RCSD'] > 1.25) & (data['ROE'] > TAUX_SANS_RISQUE)
    ]
    choix = ['Alerte (Sous-Performance)', 'Sous-Observation', 'Performant (Core)']
    data['Statut'] = np.select(conditions, choix, default='Inconnu')
    
    return data

# ==========================================
# INTERFACE UTILISATEUR & BARRE LATÉRALE
# ==========================================
st.title(" Tableau de Bord - Immobilier & Allocation")

st.sidebar.header("📁 Injecter vos données")
st.sidebar.markdown("*Mode Confidentiel : Les données sont traitées dans la RAM de votre navigateur et détruites à la fermeture.*")

# Bouton de téléchargement du gabarit
st.sidebar.download_button(
    label="📥 Télécharger le Gabarit à remplir (CSV)",
    data=get_template_csv(),
    file_name="Gabarit_Portefeuille_Immo.csv",
    mime="text/csv"
)

st.sidebar.markdown("---")

# Zone de dépôt du fichier
fichier_utilisateur = st.sidebar.file_uploader("Importez votre fichier complété (.xlsx ou .csv)", type=['xlsx', 'csv'])

# Vérification de la présence du fichier
if fichier_utilisateur is None:
    st.info("👋 Bienvenue sur le Tableau de Bord du Family Office.\n\n**Veuillez téléverser votre fichier d'actifs immobiliers dans la barre latérale pour générer les analyses.** Si vous n'avez pas de fichier, téléchargez le gabarit ci-contre.")
    st.stop()  # Arrête l'exécution ici si aucun fichier n'est chargé

# Si le fichier est présent, on lance les calculs
try:
    df = process_data(fichier_utilisateur, fichier_utilisateur.name)
except Exception as e:
    st.error(f"Erreur de lecture du fichier. Assurez-vous d'utiliser le gabarit fourni. Erreur technique : {e}")
    st.stop()

# ==========================================
# CRÉATION DES 4 ONGLETS
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Synthèse & Marché", 
    "⚖️ Outil de Décision (Inaction)", 
    "🏢 Matrice Détaillée", 
    "📖 Glossaire"
])

# --- ONGLET 1 : SYNTHÈSE & MARCHÉ ---
with tab1:
    st.header("Indicateurs de Marché Actuels")
    col1, col2, col3 = st.columns(3)
    col1.metric("Taux Sans Risque (Cible)", f"{TAUX_SANS_RISQUE*100:.2f} %")
    
    # Appel de l'API pour afficher le rendement de l'indice immobilier en temps réel
    rendement_actuel_fpi = get_real_index_cagr("XRE.TO", 5)
    col2.metric("Indice Immo Cible (XRE.TO - 5 ans)", f"{rendement_actuel_fpi*100:.2f} %")
    
    col3.metric("Valeur Nette du Portefeuille", f"{df['Equite_Nette'].sum():,.0f} $")
    
    st.divider()
    
    st.subheader("🚨 Alertes de Sous-Performance")
    alertes = df[df['Statut'] == 'Alerte (Sous-Performance)']
    
    if not alertes.empty:
        for _, row in alertes.iterrows():
            st.error(f"**{row['ID']}** - RCSD: {row['RCSD']:.2f} | ROE: {row['ROE']*100:.2f}% | Équité bloquée : {row['Equite_Nette']:,.0f} $\n\n"
                     f"*Alerte : Les métriques de cet immeuble sont inférieures aux taux cibles du marché ou ne couvrent pas la dette.*")
    else:
        st.success("✅ Aucun actif en sous-performance critique détecté.")

# --- ONGLET 2 : OUTIL DE DÉCISION (COÛT DE L'INACTION) ---
with tab2:
    st.header("Évaluation du coût de l'inaction (Avec Prise de Valeur)")
    st.write("Évaluez si la spéculation (prise de valeur estimée) justifie de conserver un actif sous-performant en trésorerie.")
    
    col_params, col_graph = st.columns([1, 2])
    
    with col_params:
        st.subheader("Paramètres de Scénario")
        immeuble_choisi = st.selectbox("Sélectionnez un immeuble à analyser :", df['ID'])
        actif = df[df['ID'] == immeuble_choisi].iloc[0]
        
        horizon = st.slider("Horizon Temporel (Années)", min_value=1, max_value=20, value=5)
        
        st.markdown("---")
        st.markdown("**1. Choix du Benchmark (L'Indice de Comparaison)**")
        
        # Calcul de l'Indice Interne (Moyenne du ROE des actifs 'Performants')
        actifs_performants = df[df['Statut'] == 'Performant (Core)']
        if not actifs_performants.empty:
            roe_interne_moyen = actifs_performants['ROE'].mean()
        else:
            roe_interne_moyen = RENDEMENT_FPI_CIBLE_DEFAUT # Par défaut si aucun immeuble n'est performant
        
        # Menu déroulant pour choisir l'indice de marché réel
        ticker_choisi = st.selectbox(
            "Choix de l'Indice de Marché Externe :",
            [
                "XRE.TO (Immobilier Canadien FPI)", 
                "VFV.TO (S&P 500 en CAD)", 
                "XIU.TO (Bourse Canadienne TSX 60)"
            ]
        )
        symbole = ticker_choisi.split(" ")[0]
        rendement_reel_externe = get_real_index_cagr(ticker=symbole, annees_historique=5)
        
        # Sélection de la stratégie par l'utilisateur
        strategie_cible = st.radio(
            "Stratégie de Réallocation :",
            ["Marché Externe (Indice en Direct)", "Force Interne (Top Performers du Portefeuille)"]
        )
        
        # Ajustement du rendement cible selon la sélection
        if strategie_cible == "Marché Externe (Indice en Direct)":
            st.info(f"📈 Le rendement historique composé sur 5 ans de **{symbole}** est de **{rendement_reel_externe*100:.2f} %** (Dividendes inclus).")
            rendement_cible = st.number_input("Rendement Cible Externe (%)", value=rendement_reel_externe*100, step=0.5) / 100
        else:
            if not actifs_performants.empty:
                st.info(f"💡 Le ROE moyen actuel de vos immeubles 'Performants' est de **{roe_interne_moyen*100:.2f} %**.")
            else:
                st.warning("Aucun immeuble n'est classé 'Performant'. Utilisation du taux externe par défaut.")
            rendement_cible = roe_interne_moyen
            
        st.markdown("---")
        st.markdown("**2. Hypothèses de Marché**")
        appreciation_annuelle = st.slider("Prise de valeur annuelle estimée de l'immeuble (%)", min_value=-5.0, max_value=15.0, value=2.0, step=0.5) / 100
        frais_sortie = st.slider("Frottement Fiscal / Frais de Vente (%)", min_value=0.0, max_value=30.0, value=15.0, step=1.0) / 100
        
    with col_graph:
        # Variables de base
        valeur_actuelle = actif['Valeur_Marchande']
        dette_actuelle = actif['Dette']
        equite_initiale = actif['Equite_Nette']
        cash_flow_annuel = actif['RNE'] - actif['Service_Dette']
        
        annees = np.arange(0, horizon + 1)
        
        # Trajectoire 1 : Statu Quo (Inaction) avec Prise de valeur
        valeur_future_immeuble = valeur_actuelle * ((1 + appreciation_annuelle) ** annees)
        equite_future = valeur_future_immeuble - dette_actuelle
        val_inaction = equite_future + (cash_flow_annuel * annees)
        
        # Trajectoire 2 : Vente immédiate et Réallocation (Action) selon le Benchmark choisi
        capital_net_reinvesti = equite_initiale * (1 - frais_sortie)
        val_action = capital_net_reinvesti * ((1 + rendement_cible) ** annees)
        
        # Graphique Plotly
        nom_legende_action = "Réallocation (Indice Externe)" if strategie_cible == "Marché Externe (Indice en Direct)" else "Réallocation (Indice Interne)"
        
        fig_df = pd.DataFrame({
            'Année': annees, 
            'Statu Quo (Immeuble conservé)': val_inaction, 
            nom_legende_action: val_action
        })
        
        fig = px.line(fig_df, x='Année', y=['Statu Quo (Immeuble conservé)', nom_legende_action],
                      labels={'value': 'Richesse Nette Totale ($)', 'variable': 'Stratégie'},
                      title=f"Projection de Richesse sur {horizon} ans - {immeuble_choisi}")
        
        fig.update_layout(hovermode="x unified", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
        st.plotly_chart(fig, use_container_width=True)

    # Conclusion du modèle
    st.divider()
    cout_inaction = val_action[-1] - val_inaction[-1]
    
    col_res1, col_res2, col_res3 = st.columns(3)
    col_res1.metric(f"Valeur finale (Immeuble)", f"{val_inaction[-1]:,.0f} $")
    col_res2.metric(f"Valeur finale (Réallocation)", f"{val_action[-1]:,.0f} $")
    
    # Inversion de la couleur : Un coût de l'inaction positif (différentiel marché > immeuble) s'affiche en rouge
    col_res3.metric(f"Différentiel (Coût de l'Inaction)", f"{cout_inaction:,.0f} $", 
                    delta=f"{-cout_inaction:,.0f} $", delta_color="normal")
    
    if cout_inaction > 0:
        st.warning(f"⚠️ **Vente Stratégique Recommandée :** Même avec une prise de valeur projetée de {appreciation_annuelle*100}%, le benchmark choisi ({strategie_cible}) surperforme l'immeuble de **{cout_inaction:,.0f} $** sur {horizon} ans après impôts. L'actif détruit de l'opportunité.")
    else:
        st.success(f"✅ **Conservation Recommandée :** Grâce à la prise de valeur projetée de {appreciation_annuelle*100}% et au coût élevé du frottement fiscal de sortie, conserver l'immeuble génère **{abs(cout_inaction):,.0f} $** de plus que le benchmark sur {horizon} ans.")

# --- ONGLET 3 : MATRICE IMMOBILIÈRE DÉTAILLÉE ---
with tab3:
    st.header("Base de données du portefeuille")
    
    # Formatage du tableau pour Streamlit (correction de applymap vers map)
    styled_df = df[['ID', 'Valeur_Marchande', 'Dette', 'Equite_Nette', 'Service_Dette', 'RCSD', 'ROE', 'Statut']].style.format({
        'Valeur_Marchande': "{:,.0f} $",
        'Dette': "{:,.0f} $",
        'Equite_Nette': "{:,.0f} $",
        'Service_Dette': "{:,.0f} $",
        'RCSD': "{:.2f}",
        'ROE': "{:.2%}"
    }).map(lambda x: 'color: #ff4b4b; font-weight: bold' if x == 'Alerte (Sous-Performance)' else ('color: #09ab3b' if x == 'Performant (Core)' else ''), subset=['Statut'])
    
    st.dataframe(styled_df, use_container_width=True, height=500)
    
# --- ONGLET 4 : GLOSSAIRE & TERMINOLOGIE ---
with tab4:
    st.header("Glossaire des thèmes institutionnels")
    
    st.markdown("""
    *   **RCSD (Ratio de Couverture du Service de la Dette) :** *Formule : Revenu Net d'Exploitation / Paiements de dette (Capital + Intérêts).* Indique la capacité d'un immeuble à payer son hypothèque. Un ratio sous 1.0 signifie que l'immeuble nécessite une injection de liquidités.
    *   **ROE (Return on Equity - Rendement sur l'Équité) :** *Formule : Flux de trésorerie net annuel / Équité Nette.* Mesure l'efficacité du capital "bloqué" dans la propriété.
    *   **Coût de l'Inaction :** La différence financière entre maintenir le statu quo sur un actif sous-performant et réallouer ce capital net vers un indice de marché (Benchmark), calculée sur un horizon donné.
    *   **Frottement Fiscal (Récupération d'amortissement) :** L'impôt payable à la vente d'un immeuble en raison des déductions pour amortissement (DPA) réclamées les années antérieures. Cet impôt réduit le produit net de la vente disponible pour réinvestissement.
    *   **Équité Nette (Équité Dormante) :** La valeur marchande actuelle de l'immeuble moins le solde hypothécaire. C'est le capital réel du portefeuille exposé au risque sur cet actif.
    """)
