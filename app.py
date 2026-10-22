"""Ponto de entrada do Streamlit: configura a página e navega entre o Plantão e a Triagem."""
import streamlit as st
from dotenv import load_dotenv

# Carrega as variáveis do .env (GOOGLE_API_KEY e LangSmith) antes de importar o grafo nas páginas
load_dotenv()

from ui import componentes as ui

# Cores e fontes ficam em .streamlit/config.toml; o CSS de ui.CSS cuida dos componentes próprios.
st.set_page_config(
    page_title="Triagem Clínica",
    page_icon=ui.AVATAR_ASSISTENTE,
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.html(ui.CSS)

# O Plantão abre primeiro: quem assume o turno vê o estado do hospital antes de triar
pagina = st.navigation(
    [
        st.Page("paginas/plantao.py", title="Plantão", icon=":material/dashboard:", default=True),
        st.Page("paginas/triagem.py", title="Triagem", icon=":material/stethoscope:"),
    ],
    position="top",
)
pagina.run()
