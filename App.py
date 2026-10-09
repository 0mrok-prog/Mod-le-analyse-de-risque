# ==========================================
# ONGLET 2 : OUTIL DE DÉCISION (COÛT DE L'INACTION & PLUS-VALUE)
# ==========================================
with tab2:
    st.header("Simulateur : Le Coût de l'Inaction (Avec Prise de Valeur)")
    st.write("Évaluez si la spéculation (prise de valeur) justifie de conserver un actif sous-performant en trésorerie.")
    
    col_params, col_graph = st.columns([1, 2])
    
    with col_params:
        st.subheader("Paramètres")
        immeuble_choisi = st.selectbox("Sélectionnez un immeuble à analyser :", df['ID'])
        actif = df[df['ID'] == immeuble_choisi].iloc[0]
        
        horizon = st.slider("Horizon Temporel (Années)", min_value=1, max_value=20, value=5)
        
        st.markdown("---")
        st.markdown("**Hypothèses de Marché**")
        # Le nouveau curseur pour la prise de valeur basée sur les comparables futurs
        appreciation_annuelle = st.slider("Prise de valeur annuelle de l'immeuble (%)", min_value=-5.0, max_value=10.0, value=2.0, step=0.5, help="Ex: Inflation ou croissance estimée du quartier.") / 100
        rendement_cible = st.number_input("Rendement Cible (Marché/Indice) %", value=RENDEMENT_FPI_CIBLE*100) / 100
        frais_sortie = st.slider("Frottement Fiscal / Frais de Vente (%)", min_value=0.0, max_value=30.0, value=15.0, step=1.0) / 100
        
    with col_graph:
        # 1. Variables de base
        valeur_actuelle = actif['Valeur_Marchande']
        dette_actuelle = actif['Dette']
        equite_initiale = actif['Equite_Nette']
        cash_flow_annuel = actif['RNE'] - actif['Service_Dette']
        
        annees = np.arange(0, horizon + 1)
        
        # 2. Trajectoire 1 : Statu Quo (Inaction) avec Prise de valeur
        # La valeur de l'immeuble augmente chaque année
        valeur_future_immeuble = valeur_actuelle * ((1 + appreciation_annuelle) ** annees)
        # L'équité est la valeur future moins la dette (simplifiée comme constante ici pour la prudence)
        equite_future = valeur_future_immeuble - dette_actuelle
        # Richesse totale = Équité de l'immeuble + Cash-flow cumulé
        val_inaction = equite_future + (cash_flow_annuel * annees)
        
        # 3. Trajectoire 2 : Vente immédiate et Réallocation (Action)
        capital_net_reinvesti = equite_initiale * (1 - frais_sortie)
        val_action = capital_net_reinvesti * ((1 + rendement_cible) ** annees)
        
        # 4. Graphique Plotly
        fig_df = pd.DataFrame({'Année': annees, 'Statu Quo (Immeuble)': val_inaction, 'Réallocation (Indice)': val_action})
        fig = px.line(fig_df, x='Année', y=['Statu Quo (Immeuble)', 'Réallocation (Indice)'],
                      labels={'value': 'Richesse Totale ($)', 'variable': 'Stratégie'},
                      title=f"Projection de Richesse sur {horizon} ans - {immeuble_choisi}")
        
        fig.update_layout(hovermode="x unified", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
        st.plotly_chart(fig, use_container_width=True)

    # Conclusion du modèle
    st.divider()
    cout_inaction = val_action[-1] - val_inaction[-1]
    
    col_res1, col_res2, col_res3 = st.columns(3)
    col_res1.metric(f"Valeur finale (Immeuble conservé)", f"{val_inaction[-1]:,.0f} $")
    col_res2.metric(f"Valeur finale (Indice)", f"{val_action[-1]:,.0f} $")
    
    # Inversion de la couleur : Un coût de l'inaction positif est mauvais (rouge), négatif est bon (vert)
    col_res3.metric(f"Différentiel (Coût de l'Inaction)", f"{cout_inaction:,.0f} $", 
                    delta=f"{-cout_inaction:,.0f} $", delta_color="normal")
    
    # Interprétation intelligente
    if cout_inaction > 0:
        st.warning(f"⚠️ **Vente Recommandée :** Même avec une prise de valeur projetée de {appreciation_annuelle*100}%, le marché boursier surperforme l'immeuble de **{cout_inaction:,.0f} $** sur {horizon} ans après impôts. L'immeuble détruit de l'opportunité.")
    else:
        st.success(f"✅ **Conservation Recommandée :** Grâce à la prise de valeur projetée de {appreciation_annuelle*100}% et au frottement fiscal de sortie, conserver l'immeuble génère **{abs(cout_inaction):,.0f} $** de plus que le marché sur {horizon} ans.")
