"""Página do plantão: visão geral do hospital para quem assume o turno."""
from datetime import datetime, timezone

import streamlit as st

from core.fila import listar_pacientes, marcar_atendido, pendencias
from core.graph import app_graph
from core.hospital import ESCALA_PLANTAO, LEITOS, TURNO
from ui import componentes as ui
from ui import plantao as up
from ui.sessao import abrir_paciente, novo_paciente

PAGINA_TRIAGEM = "paginas/triagem.py"

st.html(up.CSS)


@st.fragment(run_every="30s")
def painel():
    """Recarrega sozinho a cada 30 s, para a fila e as pendências ficarem sempre atuais."""
    agora = datetime.now(timezone.utc)
    pacientes = listar_pacientes(app_graph)

    # --- Cabeçalho ---
    col_titulo, col_botao = st.columns([6, 1.4], vertical_alignment="center")
    col_titulo.html(ui.cabecalho("Plantão", f"Turno {TURNO} · atualizado às {datetime.now():%H:%M}"))
    if col_botao.button("Nova triagem", icon=":material/person_add:", type="primary", width="stretch"):
        novo_paciente()
        st.switch_page(PAGINA_TRIAGEM)

    # --- Indicadores ---
    st.html(up.indicadores(pacientes, LEITOS, ESCALA_PLANTAO, agora))

    col_mapa, col_fila = st.columns([2.3, 1], gap="medium")

    # --- Mapa do hospital: leitos, internados e onde está cada médico ---
    with col_mapa:
        st.html(up.mapa_hospital(pacientes, agora))

    # --- Fila da triagem (mais grave primeiro) e pendências ---
    with col_fila:
        st.html(up.secao("Fila da triagem", f"{len(pacientes)} aguardando"))
        if not pacientes:
            st.html(up.fila_vazia())
        for p in pacientes:
            cor = p.classificacao or ("PEDIATRICO" if p.pediatrico else "TRIAGEM")
            with st.container(key=f"fila_{cor}_{p.thread_id}"):
                st.html(up.linha_fila(p, agora))
                abrir, atendido = st.columns(2)
                if abrir.button("Abrir", key=f"abrir_{p.thread_id}", icon=":material/chat:", width="stretch"):
                    abrir_paciente(p.thread_id, p.chegada.astimezone().strftime("%H:%M"))
                    st.switch_page(PAGINA_TRIAGEM)
                # O callback roda antes do redesenho, então a fila já aparece sem o paciente
                atendido.button("Atendido", key=f"atendido_{p.thread_id}", icon=":material/check:",
                                type="tertiary", width="stretch",
                                on_click=marcar_atendido, args=(app_graph, p.thread_id),
                                disabled=p.aguardando_aprovacao,
                                help="Responda a autorização pendente antes de liberar o paciente."
                                if p.aguardando_aprovacao else "Tira o paciente da fila.")
        st.html(up.lista_pendencias(pendencias(pacientes, agora)))


painel()
