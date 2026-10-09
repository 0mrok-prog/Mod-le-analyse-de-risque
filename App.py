import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Tableau de Bord Stratégique FO", layout="wide", page_icon="🏢")

# --- PARAMÈTRES GLOBAUX ---
TAUX_SANS_RISQUE = 0.04  # 4.00%
RENDEMENT_FPI_CIBLE = 0.08  # 8.00%

# --- CHARGEMENT ET CALCUL DES DONNÉES ---
@st.cache_data
def load_data():
    try:
        # Tente de lire le fichier Excel local
        data = pd.read_excel('portefeuille_immo.xlsx')
    except FileNotFoundError:
        # Données de secours si le fichier Excel n'est pas encore créé
        data = pd.DataFrame({
            'ID': ['Immeuble Alpha (MTL)', 'Immeuble Beta (QC)', 'Tour Gamma (Laval)', 'Immeuble Delta (IO)'],
            'Valeur_Marchande': [10000000, 12500000, 25000000, 15000000],
            'Dette': [7000000, 6000000, 10000000, 8000000],
            'RNE': [350000, 742000, 1880000, 600000],
            'Taux_Interet': [0.055, 0.048, 0.062, 0.060],
            'Amortissement_Annees': [25, 20, 25, 0] # 0 = Interest Only
        })
    
    # --- 1. MOTEUR DE CALCUL DU SERVICE DE LA DETTE ---
    r = data['Taux_Interet'] / 12
    n = data['Amortissement_Annees'] * 12
    
    # Calcul pour les prêts amortis
    paiement_annuel_amorti = (data['Dette'] * (r / (1 - (1 + r)**(-n)))) * 12
    
    # Calcul pour les prêts "Interest Only" (intérêts seulement)
    paiement_interets_seuls = data['Dette'] * data['Taux_Interet']
    
    # Applique la bonne formule selon la colonne 'Amortissement_Annees'
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

df = load_data()

st.title("🏛️ Tableau de Bord Stratégique - Immobilier & Allocation")

# --- CRÉATION DES 4 ONGLETS ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Synthèse & Marché", 
    "⚖️ Outil de Décision (Inaction)", 
    "🏢 Matrice Détaillée", 
    "📖 Glossaire"
])

# ==========================================
# ONGLET 1 : SYNTHÈSE & MARCHÉ
# ==========================================
with tab1:
    st.header("Indicateurs de Marché Actuels")
    col1, col2, col3 = st.columns(3)
    col1.metric("Taux Sans Risque (Cible)", f"{TAUX_SANS_RISQUE*100:.2f} %")
    col2.metric("Indice Immo Cible (FPI)", f"{RENDEMENT_FPI_CIBLE*100:.2f} %")
    col3.metric("Valeur Nette du Portefeuille", f"{df['Equite_Nette'].sum():,.0f} $")
    
    st.divider()
    
    st.subheader("🚨 Alertes de Sous-Performance")
    alertes = df[df['Statut'] == 'Alerte (Sous-Performance)']
    
    if not alertes.empty:
        for _, row in alertes.iterrows():
            st.error(f"**{row['ID']}** - RCSD: {row['RCSD']:.2f} | ROE: {row['ROE']*100:.2f}% | Équité bloquée : {row['Equite_Nette']:,.0f} $\n\n"
                     f"*Alerte : Les métriques de cet immeuble sont inférieures aux taux cibles du marché ou ne couvrent pas la dette.*")
    else:
        st.success("Aucun actif en sous-performance critique détecté.")

# ==========================================
# ONGLET 2 : OUTIL DE DÉCISION (COÛT DE L'INACTION)
# ==========================================
with tab2:
    st.header("Simulateur : Le Coût de l'Inaction")
    st.write("Cet outil simule la vente d'un actif sous-performant et la réallocation du capital net dans l'indice de référence.")
    
    col_params, col_graph = st.columns([1, 2])
    
    with col_params:
        st.subheader("Paramètres")
        immeuble_choisi = st.selectbox("Sélectionnez un immeuble à analyser :", df['ID'])
        actif = df[df['ID'] == immeuble_choisi].iloc[0]
        
        horizon = st.slider("Horizon Temporel (Années)", min_value=1, max_value=20, value=5)
        frais_sortie = st.slider("Frais de Sortie (Impôts + Courtage) %", min_value=0.0, max_value=30.0, value=15.0, step=1.0) / 100
        rendement_cible = st.number_input("Rendement du marché cible %", value=RENDEMENT_FPI_CIBLE*100) / 100
        
    with col_graph:
        # Données initiales
        eq_initiale = actif['Equite_Nette']
        roe_actuel = actif['ROE']
        
        # Calculs des trajectoires
        annees = np.arange(0, horizon + 1)
        val_inaction = eq_initiale * ((1 + roe_actuel) ** annees)
        
        capital_net_reinvesti = eq_initiale * (1 - frais_sortie)
        val_action = capital_net_reinvesti * ((1 + rendement_cible) ** annees)
        
        # Création du graphique Plotly
        fig_df = pd.DataFrame({'Année': annees, 'Statu Quo (Inaction)': val_inaction, 'Réallocation (Action)': val_action})
        fig = px.line(fig_df, x='Année', y=['Statu Quo (Inaction)', 'Réallocation (Action)'],
                      labels={'value': 'Valeur de l\'Équité ($)', 'variable': 'Scénario'},
                      title=f"Projection sur {horizon} ans - {immeuble_choisi}")
        
        fig.update_layout(hovermode="x unified", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
        st.plotly_chart(fig, use_container_width=True)

    # Conclusion du modèle
    st.divider()
    cout_inaction = val_action[-1] - val_inaction[-1]
    
    col_res1, col_res2, col_res3 = st.columns(3)
    col_res1.metric(f"Valeur finale (Inaction)", f"{val_inaction[-1]:,.0f} $")
    col_res2.metric(f"Valeur finale (Action)", f"{val_action[-1]:,.0f} $")
    col_res3.metric(f"Différentiel (Coût Inaction)", f"{cout_inaction:,.0f} $", 
                    delta=f"{cout_inaction:,.0f} $", delta_color="normal" if cout_inaction > 0 else "inverse")
    
    if cout_inaction > 0:
        st.warning(f"**Conclusion du Modèle :** Le rendement du marché absorbera le coût fiscal de la vente en cours de route. La vente est mathématiquement recommandée, représentant un gain d'opportunité de plus de {cout_inaction:,.0f} $ sur {horizon} ans.")
    else:
        st.success(f"**Conclusion du Modèle :** L'impôt à la vente (le frottement fiscal) est trop élevé pour être compensé par le rendement du marché sur cet horizon. Conserver l'immeuble est financièrement plus avantageux.")

# ==========================================
# ONGLET 3 : MATRICE IMMOBILIÈRE DÉTAILLÉE
# ==========================================
with tab3:
    st.header("Base de données du portefeuille")
    
    # Formatage du tableau pour Streamlit
    styled_df = df[['ID', 'Valeur_Marchande', 'Dette', 'Equite_Nette', 'Service_Dette', 'RCSD', 'ROE', 'Statut']].style.format({
        'Valeur_Marchande': "{:,.0f} $",
        'Dette': "{:,.0f} $",
        'Equite_Nette': "{:,.0f} $",
        'Service_Dette': "{:,.0f} $",
        'RCSD': "{:.2f}",
        'ROE': "{:.2%}"
    }).applymap(lambda x: 'color: #ff4b4b; font-weight: bold' if x == 'Alerte (Sous-Performance)' else ('color: #09ab3b' if x == 'Performant (Core)' else ''), subset=['Statut'])
    
    st.dataframe(styled_df, use_container_width=True, height=400)

# ==========================================
# ONGLET 4 : GLOSSAIRE & TERMINOLOGIE
# ==========================================
with tab4:
    st.header("Glossaire des thèmes institutionnels")
    
    st.markdown("""
    *   **RCSD (Ratio de Couverture du Service de la Dette) :** *Formule : Revenu Net d'Exploitation / Paiements de dette (Capital + Intérêts).*[cite: 1] Indique la capacité d'un immeuble à payer son hypothèque.[cite: 1] Un ratio sous 1.0 signifie que l'immeuble nécessite une injection de liquidités.[cite: 1]
    *   **ROE (Return on Equity - Rendement sur l'Équité) :** *Formule : Flux de trésorerie net annuel / Équité Nette.*[cite: 1] Mesure l'efficacité du capital "bloqué" dans la propriété.[cite: 1]
    *   **Coût de l'Inaction :** La différence financière entre maintenir le statu quo sur un actif sous-performant et réallouer ce capital net vers un indice de marché (Benchmark), calculée sur un horizon donné.[cite: 1]
    *   **Frottement Fiscal (Récupération d'amortissement) :** L'impôt payable à la vente d'un immeuble en raison des déductions pour amortissement (DPA) réclamées les années antérieures.[cite: 1] Cet impôt réduit le produit net de la vente disponible pour réinvestissement.[cite: 1]
    *   **Équité Nette (Équité Dormante) :** La valeur marchande actuelle de l'immeuble moins le solde hypothécaire.[cite: 1] C'est le capital réel du Family Office exposé au risque sur cet actif.[cite: 1]
    """)
