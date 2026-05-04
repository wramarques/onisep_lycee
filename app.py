import streamlit as st

st.set_page_config(page_title="Lycées GT — Orientation 2nde", layout="wide")

pg = st.navigation([
    st.Page("pages/0_Accueil.py",                   title="Accueil",                    icon="🏠"),
    st.Page("pages/1_Recherche_Etablissements.py",   title="Recherche établissements",   icon="🏫"),
    st.Page("pages/2_Simulateur_Affelnet.py",        title="Simulateur Affelnet",        icon="📊"),
])

pg.run()
