"""Página de triagem: conversa com a assistente e painel do paciente atual."""
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from core.graph import app_graph
from core.hospital import ESCALA_PLANTAO, LEITOS
from ui import componentes as ui
from ui.sessao import garantir_paciente, novo_paciente
from utils.logger import logger
from utils.text import conteudo_para_texto

# --- 1. CASOS DE EXEMPLO ---
EXEMPLOS = {
    "Adulto com dor no peito": "Paciente 58 anos, dor no peito há 30 minutos. FC 112, PA 100/70, FR 22, "
                               "SpO2 94% em ar ambiente, temperatura 36,8°C, alerta.",
    "Idoso confuso e febril": "Paciente 79 anos, confuso desde ontem. FC 118, PA 96/60, FR 24, "
                              "SpO2 93% em ar ambiente, temperatura 39,2°C.",
    "Criança com febre": "Criança de 6 anos com febre há 2 dias. FC 125, FR 28, SpO2 97%, temperatura 38,9°C, alerta.",
    "Paciente estável": "Paciente 34 anos, dor lombar leve. FC 78, PA 122/80, FR 14, SpO2 99% em ar ambiente, "
                        "temperatura 36,5°C, alerta.",
}

# --- 2. SESSÃO ---
garantir_paciente()

config = {"configurable": {"thread_id": st.session_state.thread_id}}


def executar_grafo(entrada):
    """Roda o grafo até o fim ou até a próxima pausa de aprovação, mostrando o indicador de 'digitando'."""
    with historico:
        with st.chat_message("assistant", avatar=ui.AVATAR_ASSISTENTE):
            st.html(ui.digitando())
    try:
        app_graph.invoke(entrada, config=config)
    except Exception as erro:  # API fora do ar, chave inválida, cota estourada...
        logger.exception("Falha ao executar o grafo")
        st.session_state.erro = f"Não foi possível processar a solicitação: {erro}"


def enviar_mensagem(texto: str):
    # Mostra a mensagem na hora, enquanto o agente processa
    with historico:
        st.chat_message("user", avatar=ui.AVATAR_ENFERMEIRO).markdown(texto)
    executar_grafo({"messages": [HumanMessage(content=texto)]})
    st.rerun()


snapshot = app_graph.get_state(config)
estado = snapshot.values or {}
mensagens = estado.get("messages", [])
pendentes = [i for tarefa in snapshot.tasks for i in tarefa.interrupts]

# --- 3. CABEÇALHO ---
col_titulo, col_ajuda, col_botao = st.columns([8, 1.1, 1.4], vertical_alignment="center")
col_titulo.html(ui.cabecalho(
    "Triagem", f"Paciente #{st.session_state.thread_id[:6].upper()} · desde {st.session_state.inicio}",
))
with col_ajuda.popover("Ajuda", icon=":material/help:", width="stretch"):
    st.markdown("**Classificação**")
    st.html(ui.legenda_classificacao())
    st.markdown("**Como funciona**")
    st.html(ui.como_funciona() + ui.aviso_legal())
col_botao.button("Novo paciente", icon=":material/person_add:", type="primary", width="stretch",
                 on_click=novo_paciente)

col_chat, col_painel = st.columns([1.25, 1], gap="medium")

# --- 4. CHAT ---
# Argumentos de cada chamada de ferramenta, para mostrar junto do resultado (auditoria)
argumentos = {
    tc["id"]: tc["args"]
    for m in mensagens if isinstance(m, AIMessage)
    for tc in m.tool_calls
}


def mostrar_ferramentas(bloco: list[ToolMessage], indice: int):
    """Consultas de um passo do agente: uma linha discreta que abre os detalhes."""
    itens = []
    for msg in bloco:
        nome, _ = ui.FERRAMENTAS.get(msg.name, (msg.name, ""))
        itens.append((nome, getattr(msg, "status", "success") == "error"))

    with st.container(key=f"detalhes_{indice}"):
        with st.expander(ui.rotulo_consultas(itens)):
            for msg, (nome, erro) in zip(bloco, itens):
                st.markdown(f"**{nome}**" + (" · dado inválido, a assistente pediu correção" if erro else ""))
                st.markdown(ui.formatar_argumentos(argumentos.get(msg.tool_call_id, {})))
                st.caption(conteudo_para_texto(msg.content))


def mostrar_aprovacao(pedido: dict):
    """Human-in-the-loop: a ação sensível aparece logo abaixo da pergunta da assistente."""
    with st.container(border=True, key="aprovacao"):
        st.html('<div class="tr-approval-title">Autorização necessária</div>'
                '<div class="tr-approval-sub">A ação abaixo só acontece se você aprovar.</div>'
                + ui.itens_aprovacao(pedido.get("acoes", [])))
        observacao = st.text_input("Observação (opcional)", key="obs_aprovacao",
                                   placeholder="Ex: médico já está com o paciente")
        col1, col2 = st.columns(2)
        aprovar = col1.button("Aprovar", icon=":material/check_circle:", type="primary", width="stretch")
        rejeitar = col2.button("Rejeitar", icon=":material/close:", width="stretch")
    if aprovar or rejeitar:
        executar_grafo(Command(resume={"aprovado": bool(aprovar), "observacao": observacao}))
        st.rerun()


with col_chat:
    with st.container(key="chatcard"):
        # Alturas fixas são sobrescritas pelo CSS (ui.CSS) para acompanhar a altura da tela
        historico = st.container(height=440, border=False, autoscroll=True, key="historico")
        with historico:
            if not mensagens:
                with st.chat_message("assistant", avatar=ui.AVATAR_ASSISTENTE):
                    st.html(ui.saudacao())
                with st.container(key="exemplos"):
                    st.caption("Ou experimente um caso de exemplo:")
                    colunas = st.columns(2)
                    for i, (rotulo, texto) in enumerate(EXEMPLOS.items()):
                        if colunas[i % 2].button(rotulo, key=f"exemplo_{i}", width="stretch"):
                            enviar_mensagem(texto)

            bloco_ferramentas: list[ToolMessage] = []
            for indice, msg in enumerate(mensagens):
                if isinstance(msg, ToolMessage):
                    bloco_ferramentas.append(msg)
                    continue
                if bloco_ferramentas:
                    mostrar_ferramentas(bloco_ferramentas, indice)
                    bloco_ferramentas = []

                if isinstance(msg, HumanMessage):
                    st.chat_message("user", avatar=ui.AVATAR_ENFERMEIRO).markdown(conteudo_para_texto(msg.content))
                elif isinstance(msg, AIMessage):
                    texto = conteudo_para_texto(msg.content)
                    if texto.strip():
                        st.chat_message("assistant", avatar=ui.AVATAR_ASSISTENTE).markdown(texto)
            if bloco_ferramentas:
                mostrar_ferramentas(bloco_ferramentas, len(mensagens))

            if pendentes:
                mostrar_aprovacao(pendentes[0].value)

            if "erro" in st.session_state:
                st.error(st.session_state.pop("erro"), icon=":material/cloud_off:")

        with st.container(key="entrada"):
            user_input = st.chat_input(
                "Responda a autorização acima para continuar" if pendentes
                else f"Escreva para a {ui.NOME_ASSISTENTE}: idade, queixa e sinais vitais...",
                disabled=bool(pendentes),
            )

# --- 5. PAINEL DO PACIENTE ---
with col_painel:
    with st.container(height=520, border=False, key="painel"):
        st.html(ui.resumo_paciente(estado) + ui.sinais_vitais(estado) + ui.recursos_hospital(LEITOS, ESCALA_PLANTAO))

if user_input:
    enviar_mensagem(user_input)
