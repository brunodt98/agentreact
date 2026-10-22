"""
Paciente atual da sessão. Cada paciente é uma "thread" do LangGraph: o histórico vive no
checkpointer do grafo (fonte única da verdade) e o Streamlit só guarda o thread_id.
"""
import uuid
from datetime import datetime

import streamlit as st


def novo_paciente():
    abrir_paciente(str(uuid.uuid4()), datetime.now().strftime("%H:%M"))


def abrir_paciente(thread_id: str, inicio: str):
    st.session_state.thread_id = thread_id
    st.session_state.inicio = inicio
    st.session_state.pop("erro", None)


def garantir_paciente():
    if "thread_id" not in st.session_state:
        novo_paciente()
    st.session_state.setdefault("inicio", datetime.now().strftime("%H:%M"))
