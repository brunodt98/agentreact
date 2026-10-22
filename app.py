import uuid
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

# Carrega as variáveis do .env (GOOGLE_API_KEY e LangSmith) antes de importar o grafo
load_dotenv()

# Importa o nosso grafo compilado do backend
from core.graph import app_graph
from ui import componentes as ui
from utils.logger import logger
from utils.text import conteudo_para_texto

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
# Cores e fontes ficam em .streamlit/config.toml; o CSS de ui.CSS cuida dos componentes próprios.
st.set_page_config(
    page_title="Triagem Clínica",
    page_icon=ui.AVATAR_ASSISTENTE,
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.html(ui.CSS)

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
# Cada paciente é uma "thread" do LangGraph. O histórico vive no checkpointer
# do grafo (fonte única da verdade); o Streamlit só guarda o thread_id.


def novo_paciente():
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.inicio = datetime.now().strftime("%H:%M")
    st.session_state.pop("erro", None)


if "thread_id" not in st.session_state:
    novo_paciente()
st.session_state.setdefault("inicio", datetime.now().strftime("%H:%M"))

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

# --- 3. BARRA LATERAL (ajuda; começa recolhida) ---
with st.sidebar:
    st.subheader("Classificação")
    st.html(ui.legenda_classificacao())
    st.subheader("Como funciona")
    st.markdown(
        "- **Sinais de alarme** (dor torácica, AVC, sangramento...) são detectados por regra e elevam o risco para vermelho.\n"
        "- O **NEWS2** usa 7 parâmetros e vale a partir de 16 anos.\n"
        "- Cada cartão de sinal vital mostra quantos pontos somou."
    )
    st.html(ui.aviso_legal())

# --- 4. CABEÇALHO E CLASSIFICAÇÃO ---
col_titulo, col_botao = st.columns([5, 1], vertical_alignment="center")
col_titulo.html(ui.cabecalho(st.session_state.thread_id[:6].upper(), st.session_state.inicio))
col_botao.button("Novo paciente", icon=":material/person_add:", type="primary", width="stretch",
                 on_click=novo_paciente)
st.html(ui.faixa_classificacao(estado))

col_chat, col_painel = st.columns([3, 2], gap="medium")

# --- 5. CHAT ---
# Argumentos de cada chamada de ferramenta, para mostrar junto do resultado (auditoria)
argumentos = {
    tc["id"]: tc["args"]
    for m in mensagens if isinstance(m, AIMessage)
    for tc in m.tool_calls
}


def mostrar_ferramentas(bloco: list[ToolMessage], indice: int):
    """Consultas de um passo do agente: pílulas resumidas e os detalhes recolhidos logo abaixo."""
    itens = []
    for msg in bloco:
        nome, _ = ui.FERRAMENTAS.get(msg.name, (msg.name, ""))
        itens.append((nome, getattr(msg, "status", "success") == "error"))
    st.html(ui.pilulas_ferramentas(itens))

    with st.container(key=f"detalhes_{indice}"):
        with st.expander("Ver detalhes das consultas", icon=":material/fact_check:"):
            for msg, (nome, erro) in zip(bloco, itens):
                st.markdown(f"**{nome}**" + (" · dado inválido, o assistente pediu correção" if erro else ""))
                st.markdown(ui.formatar_argumentos(argumentos.get(msg.tool_call_id, {})))
                st.caption(conteudo_para_texto(msg.content))


with col_chat:
    with st.container(key="chatcard"):
        st.html(ui.cabecalho_chat())

        # Alturas fixas são sobrescritas pelo CSS (ui.CSS) para acompanhar a altura da tela
        historico = st.container(height=420, border=False, autoscroll=True, key="historico")
        with historico:
            if not mensagens:
                with st.chat_message("assistant", avatar=ui.AVATAR_ASSISTENTE):
                    st.html(ui.saudacao())
                with st.container(key="exemplos"):
                    st.caption("Experimente um caso de exemplo:")
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

            if "erro" in st.session_state:
                st.error(st.session_state.pop("erro"), icon=":material/cloud_off:")

        with st.container(key="entrada"):
            user_input = st.chat_input(
                "Aguardando sua aprovação ao lado..." if pendentes
                else "Descreva o paciente: idade, queixa, FC, PA, FR, SpO2, temperatura, consciência...",
                disabled=bool(pendentes),
            )

# --- 6. PAINEL DO PACIENTE ---
with col_painel:
    painel = st.container(height=500, border=False, key="painel")
    with painel:
        # Human-in-the-loop: ações sensíveis aguardam aprovação no topo do painel, sempre à vista
        if pendentes:
            pedido = pendentes[0].value
            with st.container(border=True, key="aprovacao"):
                st.html('<div class="tr-approval-title">Autorização necessária</div>'
                        '<div class="tr-sub">O assistente quer executar a ação abaixo. Ela só acontece se você aprovar.</div>'
                        + ui.itens_aprovacao(pedido.get("acoes", [])))
                observacao = st.text_input("Observação (opcional)", key="obs_aprovacao",
                                           placeholder="Ex: médico já está com o paciente")
                col1, col2 = st.columns(2)
                aprovar = col1.button("Aprovar", icon=":material/check_circle:", type="primary", width="stretch")
                rejeitar = col2.button("Rejeitar", icon=":material/cancel:", width="stretch")

            if aprovar or rejeitar:
                executar_grafo(Command(resume={"aprovado": bool(aprovar), "observacao": observacao}))
                st.rerun()

        st.html(ui.cartoes_sinais_vitais(estado))

if user_input:
    enviar_mensagem(user_input)
