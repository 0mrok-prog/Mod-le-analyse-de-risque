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
        historique = yf.Ticker(ticker).history(period=f"{annees_historique}y")
        if historique.empty:
            return RENDEMENT_FPI_CIBLE_DEFAUT
            
        prix_initial = historique['Close'].iloc[0]
        prix_final = historique['Close'].iloc[-1]
        
        tcac = (prix_final / prix_initial) ** (1 / annees_historique) - 1
        return tcac
    except Exception:
        return RENDEMENT_FPI_CIBLE_DEFAUT

# --- GÉNÉRATEUR DE GABARIT (TEMPLATE) ---
@st.cache_data
def get_template_csv():
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
    if filename.endswith('.csv'):
        data = pd.read_csv(file)
    else:
        data = pd.read_excel(file)
        
    r = data['Taux_Interet'] / 12
    n = data['Amortissement_Annees'] * 12
    
    r_safe = np.where(r == 0, 1e-10, r) 
    paiement_annuel_amorti = (data['Dette'] * (r_safe / (1 - (1 + r_safe)**(-n)))) * 12
    paiement_interets_seuls = data['Dette'] * data['Taux_Interet']
    
    data['Service_Dette'] = np.where(data['Amortissement_Annees'] > 0, paiement_annuel_amorti, paiement_interets_seuls)
    
    data['Equite_Nette'] = data['Valeur_Marchande'] - data['Dette']
    data['RCSD'] = data['RNE'] / data['Service_Dette']
    data['ROE'] = (data['RNE'] - data['Service_Dette']) / data['Equite_Nette']
    
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
st.title("🏛️ Tableau de Bord - Immobilier & Allocation")

st.sidebar.header("📁 Injecter vos données")
st.sidebar.markdown("*Mode Confidentiel : Les données sont traitées dans la RAM de votre navigateur et détruites à la fermeture.*")

st.sidebar.download_button(
    label="📥 Télécharger le Gabarit à remplir (CSV)",
    data=get_template_csv(),
    file_name="Gabarit_Portefeuille_Immo.csv",
    mime="text/csv"
)

st.sidebar.markdown("---")

fichier_utilisateur = st.sidebar.file_uploader("Importez votre fichier complété (.xlsx ou .csv)", type=['xlsx', 'csv'])

if fichier_utilisateur is None:
    st.info("👋 Bienvenue sur le Tableau de Bord du Family Office.\n\n**Veuillez téléverser votre fichier d'actifs immobiliers dans la barre latérale pour générer les analyses.**")
    st.stop()

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
    
    rendement_actuel_fpi = get_real_index_cagr("XRE.TO", 5)
    col2.metric("Indice Immo Cible (XRE.TO - 5 ans)", f"{rendement_actuel_fpi*100:.2f} %")
    
    col3.metric("Valeur Nette du Portefeuille", f"{df['Equite_Nette'].sum():,.0f} $")
    
    st.divider()
    
    st.subheader("🚨 Alertes de Sous-Performance")
    alertes = df[df['Statut'] == 'Alerte (Sous-Performance)']
    
    if not alertes.empty:
        for _, row in alertes.iterrows():
            st.error(f"**{row['ID']}** - RCSD: {row['RCSD']:.2f} | ROE: {row['ROE']*100:.2f}% | Équité bloquée : {row['Equite_Nette']:,.0f} $\n\n"
                     f"*L'immeuble détruit de l'opportunité. Considérez une analyse dans l'Outil de Décision.*")
    else:
        st.success("✅ Aucun actif en sous-performance critique détecté.")

# --- ONGLET 2 : OUTIL DE DÉCISION (COÛT DE L'INACTION) ---
with tab2:
    st.header("L'Outil de Décision : Bilan à terme")
    st.write("Ce module compare concrètement ce qu'il vous restera dans les poches à la fin de l'horizon choisi selon deux stratégies.")
    
    col_params, col_graph = st.columns([1, 2])
    
    with col_params:
        st.subheader("Paramètres de Scénario")
        
        immeuble_choisi = st.selectbox("Sélectionnez un immeuble à analyser :", df['ID'].tolist())
        actif = df[df['ID'] == immeuble_choisi].iloc[0]
        
        horizon = st.slider("Horizon Temporel (Années)", min_value=1, max_value=20, value=5)
        
        st.markdown("---")
        st.markdown("**1. Choix du Benchmark (L'Indice)**")
        
        actifs_performants = df[df['Statut'] == 'Performant (Core)']
        roe_interne_moyen = actifs_performants['ROE'].mean() if not actifs_performants.empty else RENDEMENT_FPI_CIBLE_DEFAUT
        
        strategie_cible = st.radio(
            "Stratégie de Réallocation :",
            ["Marché Externe (Indice en Direct)", "Force Interne (Top Performers du Portefeuille)", "Fonds Custom (Saisie manuelle)"]
        )
        
        if strategie_cible == "Marché Externe (Indice en Direct)":
            ticker_choisi = st.selectbox("Indice :", ["XRE.TO (FPI)", "VFV.TO (S&P 500)", "XIU.TO (TSX 60)"])
            symbole = ticker_choisi.split(" ")[0]
            rendement_reel_externe = get_real_index_cagr(ticker=symbole, annees_historique=5)
            rendement_cible = st.number_input("Rendement Cible (%)", value=rendement_reel_externe*100, step=0.5) / 100
            nom_action = f"Vente et Bourse ({symbole})"
        elif strategie_cible == "Force Interne (Top Performers du Portefeuille)":
            if not actifs_performants.empty:
                st.info(f"💡 Le ROE moyen de vos immeubles 'Performants' est de **{roe_interne_moyen*100:.2f} %**.")
            else:
                st.warning("Aucun immeuble n'est classé 'Performant'.")
            rendement_cible = roe_interne_moyen
            nom_action = "Vente et Réinvestissement (Interne)"
        else:
            nom_fonds_custom = st.text_input("Nom du fonds :", value="Fonds Privé XYZ")
            rendement_cible = st.number_input("Rendement historique (%) :", value=10.0, step=0.5) / 100
            nom_action = f"Vente et {nom_fonds_custom}"
            
        st.markdown("---")
        st.markdown("**2. Hypothèses de Marché**")
        appreciation_annuelle = st.slider("Prise de valeur annuelle estimée de l'immeuble (%)", min_value=-5.0, max_value=15.0, value=2.0, step=0.5) / 100
        frais_sortie = st.slider("Frottement Fiscal / Frais de Vente (%)", min_value=0.0, max_value=30.0, value=15.0, step=1.0) / 100
        
    with col_graph:
        # --- CALCULS CLARIFIÉS POUR L'ANNÉE FINALE ---
        equite_initiale = actif['Equite_Nette']
        cash_flow_annuel = actif['RNE'] - actif['Service_Dette']
        
        # Stratégie 1 : Conserver (Statu Quo)
        valeur_future_immeuble = actif['Valeur_Marchande'] * ((1 + appreciation_annuelle) ** horizon)
        equite_future = valeur_future_immeuble - actif['Dette']
        gain_capital_immo = equite_future - equite_initiale
        cash_flow_cumule = cash_flow_annuel * horizon
        richesse_totale_inaction = equite_initiale + gain_capital_immo + cash_flow_cumule
        
        # Stratégie 2 : Vendre et Réallouer (Action)
        capital_net_reinvesti = equite_initiale * (1 - frais_sortie)
        richesse_totale_action = capital_net_reinvesti * ((1 + rendement_cible) ** horizon)
        rendement_marche_cumule = richesse_totale_action - capital_net_reinvesti
        
        # --- GRAPHIQUE À BARRES EMPILÉES ---
        df_bar = pd.DataFrame({
            "Stratégie": [
                "1. Conserver (Statu Quo)", "1. Conserver (Statu Quo)", "1. Conserver (Statu Quo)",
                f"2. {nom_action}", f"2. {nom_action}"
            ],
            "Composante": [
                "Équité de base", "Prise de Valeur Immo", "Cash-Flow Net (Cumulé)",
                "Capital investi (Après impôts)", "Rendements Composés de l'Indice"
            ],
            "Montant ($)": [
                equite_initiale, gain_capital_immo, cash_flow_cumule,
                capital_net_reinvesti, rendement_marche_cumule
            ]
        })
        
        couleurs = {
            "Équité de base": "#1f77b4", 
            "Prise de Valeur Immo": "#aec7e8", 
            "Cash-Flow Net (Cumulé)": "#ffbb78",
            "Capital investi (Après impôts)": "#2ca02c", 
            "Rendements Composés de l'Indice": "#98df8a"
        }
        
        fig = px.bar(df_bar, x="Stratégie", y="Montant ($)", color="Composante",
                     title=f"D'où proviendra votre richesse dans {horizon} ans ?",
                     color_discrete_map=couleurs, text_auto='.2s')
        
        fig.update_layout(barmode='stack', hovermode="y unified")
        st.plotly_chart(fig, use_container_width=True)
        
        # --- DONNÉES DE L'IMMEUBLE ANALYSÉ (LA RADIOGRAPHIE) ---
        st.markdown("---")
        st.subheader(f"📊 Profil actuel de l'immeuble : {immeuble_choisi}")
        
        # Couleur du statut
        couleur_statut = "🔴" if actif['Statut'] == 'Alerte (Sous-Performance)' else "✅" if actif['Statut'] == 'Performant (Core)' else "🟡"
        
        col_met1, col_met2, col_met3, col_met4 = st.columns(4)
        col_met1.metric("Valeur Marchande", f"{actif['Valeur_Marchande']:,.0f} $")
        col_met2.metric("Dette Hypothécaire", f"{actif['Dette']:,.0f} $")
        col_met3.metric("Équité Nette", f"{actif['Equite_Nette']:,.0f} $")
        col_met4.markdown(f"**Statut**<br>{couleur_statut} {actif['Statut']}", unsafe_allow_html=True)
        
        col_met5, col_met6, col_met7, col_met8 = st.columns(4)
        col_met5.metric("Revenu Net (RNE)", f"{actif['RNE']:,.0f} $")
        col_met6.metric("Service de la Dette", f"{actif['Service_Dette']:,.0f} $")
        col_met7.metric("RCSD", f"{actif['RCSD']:.2f}")
        col_met8.metric("ROE Actuel", f"{actif['ROE']*100:.2f} %")

    # --- CONCLUSION CLAIRE ---
    st.divider()
    cout_inaction = richesse_totale_action - richesse_totale_inaction
    
    st.subheader(f"Le Bilan dans {horizon} ans")
    col_res1, col_res2, col_res3 = st.columns(3)
    col_res1.metric(f"Richesse si on CONSERVE", f"{richesse_totale_inaction:,.0f} $")
    col_res2.metric(f"Richesse si on VEND", f"{richesse_totale_action:,.0f} $")
    
    if cout_inaction > 0:
        col_res3.metric(f"Perte d'Opportunité", f"- {cout_inaction:,.0f} $", delta="Vous laissez de l'argent sur la table", delta_color="inverse")
        st.error(f"⚠️ **Interprétation :** En choisissant de ne rien faire, vous perdez mathématiquement **{cout_inaction:,.0f} $** en création de richesse sur {horizon} ans. Le marché est beaucoup plus performant que l'exploitation de cet immeuble, même après avoir payé {frais_sortie*100}% d'impôts et frais à la revente.")
    else:
        col_res3.metric(f"Avantage de Conserver", f"+ {abs(cout_inaction):,.0f} $", delta="L'immeuble est le meilleur choix", delta_color="normal")
        st.success(f"✅ **Interprétation :** Vendre cet immeuble serait une erreur. À cause du coût élevé de sortie (impôts) et de sa performance (RNE + Prise de valeur), le conserver vous rapporte **{abs(cout_inaction):,.0f} $** de plus que de le transférer ailleurs.")

# --- ONGLET 3 : MATRICE IMMOBILIÈRE DÉTAILLÉE ---
with tab3:
    st.header("Base de données du portefeuille")
    
    # 1. Copie des colonnes pour l'affichage
    df_matrice = df[['ID', 'Valeur_Marchande', 'Dette', 'Equite_Nette', 'Service_Dette', 'RCSD', 'ROE', 'Statut']].copy()
    
    # 2. Utilisation du nom de l'immeuble comme nom de ligne (enlève les numéros)
    df_matrice.set_index('ID', inplace=True)
    
    # 3. Remplacement par des émojis universels compatibles à 100%
    df_matrice['Statut'] = df_matrice['Statut'].replace({
        'Alerte (Sous-Performance)': '🚨 Alerte',
        'Sous-Observation': '⚠️ Sous-Observation',
        'Performant (Core)': '✅ Performant'
    })
    
    # 4. Formatage des chiffres et coloration CSS robuste
    styled_df = df_matrice.style.format({
        'Valeur_Marchande': "{:,.0f} $",
        'Dette': "{:,.0f} $",
        'Equite_Nette': "{:,.0f} $",
        'Service_Dette': "{:,.0f} $",
        'RCSD': "{:.2f}",
        'ROE': "{:.2%}"
    }).map(lambda x: 'color: #ff4b4b; font-weight: bold' if 'Alerte' in str(x) else ('color: #09ab3b; font-weight: bold' if 'Performant' in str(x) else 'color: #d4a017'), subset=['Statut'])
    
    # Affichage du tableau
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
