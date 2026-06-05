"""CustoClima — router de navegação"""
import sys
sys.path.insert(0, ".")
import streamlit as st

st.set_page_config(
    page_title="CustoClima",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation([
    st.Page("pages/home.py",                       title="Alertas de Compra",             icon="🚨", default=True),
    st.Page("pages/1_Previsao_Proximos_Meses.py",  title="Previsão dos Próximos Meses",   icon="📅"),
    st.Page("pages/2_O_Modelo_Acerta.py",          title="O Modelo Acerta?",              icon="📊"),
    st.Page("pages/4_Como_Funciona.py",            title="Como Funciona",                 icon="🔬"),
    st.Page("pages/5_Entendendo_o_Site.py",        title="Entendendo o Site",             icon="📖"),
])
pg.run()
