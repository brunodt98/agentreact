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
# Cores e fontes ficam em .streamlit/config.toml; o CSS abaixo cuida dos componentes próprios.
st.set_page_config(
    page_title="Triagem Clínica",
    page_icon=":material/monitor_heart:",
    layout="wide",
)
st.html(ui.CSS)

AVATAR_ENFERMEIRO = ":material/person:"
AVATAR_ASSISTENTE = ":material/monitor_heart:"

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


def executar_grafo(entrada, local=None):
    """Roda o grafo até o fim ou até a próxima pausa de aprovação, com tratamento de erro."""
    try:
        with (local or st.container()), st.spinner("Analisando o caso..."):
            app_graph.invoke(entrada, config=config)
    except Exception as erro:  # API fora do ar, chave inválida, cota estourada...
        logger.exception("Falha ao executar o grafo")
        st.session_state.erro = f"Não foi possível processar a solicitação: {erro}"


def enviar_mensagem(texto: str):
    # Mostra a mensagem na hora, enquanto o agente processa
    with historico:
        st.chat_message("user", avatar=AVATAR_ENFERMEIRO).write(texto)
    executar_grafo({"messages": [HumanMessage(content=texto)]}, local=historico)
    st.rerun()


snapshot = app_graph.get_state(config)
estado = snapshot.values or {}
mensagens = estado.get("messages", [])
pendentes = [i for tarefa in snapshot.tasks for i in tarefa.interrupts]

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.button("Novo paciente", icon=":material/person_add:", type="primary",
              width="stretch", on_click=novo_paciente)

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
st.html(ui.cabecalho(st.session_state.thread_id[:6].upper(), st.session_state.inicio))
st.html(ui.faixa_classificacao(estado))

col_chat, col_painel = st.columns([3, 2], gap="large")

# --- 5. PAINEL DO PACIENTE ---
# Alturas fixas são sobrescritas pelo CSS (ui.CSS) para acompanhar a altura da tela
painel = col_painel.container(height=500, border=False, key="painel")

# --- 6. CONVERSA ---
# Argumentos de cada chamada de ferramenta, para mostrar junto do resultado (auditoria)
argumentos = {
    tc["id"]: tc["args"]
    for m in mensagens if isinstance(m, AIMessage)
    for tc in m.tool_calls
}


def mostrar_ferramentas(bloco: list[ToolMessage]):
    """Agrupa as ferramentas de um mesmo passo do agente numa única bolha, com detalhes recolhidos."""
    with st.chat_message("assistant", avatar=AVATAR_ASSISTENTE):
        st.caption("Consultas realizadas")
        for msg in bloco:
            nome, icone = ui.FERRAMENTAS.get(msg.name, (msg.name, ":material/build:"))
            if getattr(msg, "status", "success") == "error":
                nome, icone = f"{nome} · dado inválido, pedindo correção", ":material/error:"
            with st.expander(nome, icon=icone):
                st.markdown("**Dados enviados**")
                st.markdown(ui.formatar_argumentos(argumentos.get(msg.tool_call_id, {})))
                st.markdown("**Resultado**")
                st.text(conteudo_para_texto(msg.content))


with col_chat:
    historico = st.container(height=500, border=False, autoscroll=True, key="historico")
    with historico:
        if not mensagens:
            st.html(ui.boas_vindas())
            st.caption("Ou comece por um caso de exemplo:")
            colunas = st.columns(2)
            for i, (rotulo, texto) in enumerate(EXEMPLOS.items()):
                if colunas[i % 2].button(rotulo, key=f"exemplo_{i}", width="stretch"):
                    enviar_mensagem(texto)

        bloco_ferramentas: list[ToolMessage] = []
        for msg in mensagens:
            if isinstance(msg, ToolMessage):
                bloco_ferramentas.append(msg)
                continue
            if bloco_ferramentas:
                mostrar_ferramentas(bloco_ferramentas)
                bloco_ferramentas = []

            if isinstance(msg, HumanMessage):
                st.chat_message("user", avatar=AVATAR_ENFERMEIRO).write(conteudo_para_texto(msg.content))
            elif isinstance(msg, AIMessage):
                texto = conteudo_para_texto(msg.content)
                if texto.strip():
                    st.chat_message("assistant", avatar=AVATAR_ASSISTENTE).write(texto)
        if bloco_ferramentas:
            mostrar_ferramentas(bloco_ferramentas)

    if "erro" in st.session_state:
        st.error(st.session_state.pop("erro"), icon=":material/cloud_off:")

# --- 7. HUMAN-IN-THE-LOOP: aprovação de ações sensíveis (no topo do painel, sempre à vista) ---
with painel:
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
            executar_grafo(Command(resume={"aprovado": bool(aprovar), "observacao": observacao}), local=historico)
            st.rerun()

    st.html(ui.cartoes_sinais_vitais(estado))

# --- 8. ENTRADA DO ENFERMEIRO ---
user_input = st.chat_input(
    "Descreva o paciente: idade, queixa, FC, PA, FR, SpO2 (ar ambiente ou O2), temperatura, consciência...",
    disabled=bool(pendentes),
)

if user_input:
    enviar_mensagem(user_input)
