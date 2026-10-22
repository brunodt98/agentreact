import json
import uuid

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

# Carrega as variáveis do .env (GOOGLE_API_KEY e LangSmith) antes de importar o grafo
load_dotenv()

# Importa o nosso grafo compilado do backend
from core.graph import app_graph
from utils.logger import logger
from utils.text import conteudo_para_texto

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Triagem Inteligente",
    page_icon="🏥",
    layout="centered"
)

CORES = {
    "VERMELHO": ("🔴", "#d32f2f"),
    "AMARELO": ("🟡", "#f9a825"),
    "VERDE": ("🟢", "#2e7d32"),
}

ROTULOS_SINAIS = {
    "frequencia_cardiaca": ("FC", "bpm"),
    "pressao_sistolica": ("PAS", "mmHg"),
    "frequencia_respiratoria": ("FR", "irpm"),
    "temperatura": ("Temp", "°C"),
    "nivel_consciencia": ("Consciência", ""),
}

# --- 2. SESSÃO ---
# Cada paciente é uma "thread" do LangGraph. O histórico vive no checkpointer
# do grafo (fonte única da verdade); o Streamlit só guarda o thread_id.
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

config = {"configurable": {"thread_id": st.session_state.thread_id}}


def executar_grafo(entrada):
    """Roda o grafo até o fim ou até a próxima pausa de aprovação, com tratamento de erro."""
    try:
        with st.spinner("Analisando protocolos clínicos..."):
            app_graph.invoke(entrada, config=config)
    except Exception as erro:  # API fora do ar, chave inválida, cota estourada...
        logger.exception("Falha ao executar o grafo")
        st.session_state.erro = f"Não foi possível processar a solicitação: {erro}"


snapshot = app_graph.get_state(config)
estado = snapshot.values or {}
mensagens = estado.get("messages", [])
pendentes = [i for tarefa in snapshot.tasks for i in tarefa.interrupts]

# --- 3. PAINEL LATERAL (estado estruturado do paciente) ---
with st.sidebar:
    st.header("📋 Paciente atual")

    classificacao = estado.get("classificacao")
    if classificacao:
        emoji, cor = CORES[classificacao]
        st.markdown(
            f"<div style='background:{cor};color:white;padding:12px;border-radius:8px;"
            f"text-align:center;font-weight:bold;font-size:1.2em'>{emoji} {classificacao}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("Classificação ainda não definida.")

    if estado.get("escore_mews") is not None:
        st.metric("Escore MEWS", estado["escore_mews"], help=f"Classificação pelo MEWS: {estado.get('classificacao_mews')}")

    if estado.get("red_flags"):
        st.error("**Sinais de alarme:**\n" + "\n".join(f"- {f}" for f in estado["red_flags"]))

    if estado.get("emergencia_acionada"):
        st.success("🚨 Equipe de emergência acionada")

    sinais = estado.get("sinais_vitais") or {}
    if sinais:
        st.subheader("Sinais vitais")
        for campo, valor in sinais.items():
            rotulo, unidade = ROTULOS_SINAIS.get(campo, (campo, ""))
            st.write(f"**{rotulo}:** {valor} {unidade}")

    st.divider()
    if st.button("➕ Novo paciente", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.pop("erro", None)
        st.rerun()

# --- 4. CABEÇALHO E HISTÓRICO ---
st.title("🏥 Assistente de Triagem Hospitalar")
st.markdown("Insira os dados do paciente para iniciar a classificação de risco.")

# Argumentos de cada chamada de ferramenta, para mostrar junto do resultado (auditoria)
argumentos = {
    tc["id"]: tc["args"]
    for m in mensagens if isinstance(m, AIMessage)
    for tc in m.tool_calls
}

for msg in mensagens:
    if isinstance(msg, HumanMessage):
        st.chat_message("user").write(conteudo_para_texto(msg.content))
    elif isinstance(msg, AIMessage):
        texto = conteudo_para_texto(msg.content)
        if texto.strip():
            st.chat_message("assistant").write(texto)
    elif isinstance(msg, ToolMessage):
        with st.chat_message("assistant", avatar="🔧"):
            with st.expander(f"Ferramenta: `{msg.name}`"):
                st.caption("Argumentos")
                st.code(json.dumps(argumentos.get(msg.tool_call_id, {}), ensure_ascii=False, indent=2), language="json")
                st.caption("Resultado")
                st.write(conteudo_para_texto(msg.content))

if "erro" in st.session_state:
    st.error(st.session_state.pop("erro"))

# --- 5. HUMAN-IN-THE-LOOP: aprovação de ações sensíveis ---
if pendentes:
    pedido = pendentes[0].value
    with st.container(border=True):
        st.warning("⚠️ **O agente solicita autorização para executar uma ação:**")
        for acao in pedido.get("acoes", []):
            st.markdown(f"**{acao['ferramenta']}**")
            st.json(acao["argumentos"])
        observacao = st.text_input("Observação (opcional)", key="obs_aprovacao")
        col1, col2 = st.columns(2)
        aprovar = col1.button("✅ Aprovar", type="primary", use_container_width=True)
        rejeitar = col2.button("❌ Rejeitar", use_container_width=True)

    if aprovar or rejeitar:
        executar_grafo(Command(resume={"aprovado": bool(aprovar), "observacao": observacao}))
        st.rerun()

# --- 6. INTERAÇÃO DO USUÁRIO ---
user_input = st.chat_input(
    "Ex: Paciente 45 anos, dor no peito, PA 140/90, FC 110...",
    disabled=bool(pendentes),
)

if user_input:
    st.chat_message("user").write(user_input)
    # Passamos apenas a nova mensagem; o checkpointer lembra do resto
    executar_grafo({"messages": [HumanMessage(content=user_input)]})
    st.rerun()
