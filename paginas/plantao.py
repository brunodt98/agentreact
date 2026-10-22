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
    col_titulo, col_botao = st.columns([5, 1], vertical_alignment="center")
    col_titulo.html(ui.cabecalho(
        "Plantão", f"Visão geral do hospital · turno {TURNO}",
        [f"Atualizado {datetime.now():%H:%M}", "Atualiza a cada 30 s"],
    ))
    if col_botao.button("Nova triagem", icon=":material/person_add:", type="primary", width="stretch"):
        novo_paciente()
        st.switch_page(PAGINA_TRIAGEM)

    # --- Indicadores ---
    st.html(up.indicadores(pacientes, LEITOS, ESCALA_PLANTAO, agora))

    col_fila, col_lado = st.columns([3, 2], gap="medium")

    # --- Fila de pacientes (mais grave primeiro) ---
    with col_fila:
        st.html(up.secao("Fila de pacientes", len(pacientes)))
        if not pacientes:
            st.html(up.fila_vazia())
        for p in pacientes:
            cor = p.classificacao or ("PEDIATRICO" if p.pediatrico else "TRIAGEM")
            with st.container(key=f"fila_{cor}_{p.thread_id}"):
                info, acoes = st.columns([5, 1.2], vertical_alignment="center")
                info.html(up.linha_fila(p, agora))
                with acoes:
                    if st.button("Abrir", key=f"abrir_{p.thread_id}", icon=":material/open_in_new:", width="stretch"):
                        abrir_paciente(p.thread_id, p.chegada.astimezone().strftime("%H:%M"))
                        st.switch_page(PAGINA_TRIAGEM)
                    # O callback roda antes do redesenho, então a fila já aparece sem o paciente
                    st.button("Atendido", key=f"atendido_{p.thread_id}", icon=":material/check:", width="stretch",
                              on_click=marcar_atendido, args=(app_graph, p.thread_id),
                              disabled=p.aguardando_aprovacao,
                              help="Responda a autorização pendente antes de liberar o paciente."
                              if p.aguardando_aprovacao else "Tira o paciente da fila.")

    # --- Pendências, leitos e equipe ---
    with col_lado:
        itens = pendencias(pacientes, agora)
        st.html(up.secao("Pendências", len(itens)))
        st.html(up.lista_pendencias(itens))
        st.html(up.secao("Leitos"))
        st.html(up.ocupacao_leitos(LEITOS))
        st.html(up.secao("Equipe de plantão"))
        st.html(up.equipe(ESCALA_PLANTAO, TURNO))


painel()
