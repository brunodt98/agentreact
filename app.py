import streamlit as st
import uuid
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

# Carrega as variáveis do .env (OpenAI/Gemini e LangSmith) antes de importar o grafo
load_dotenv()

# Importa o nosso grafo compilado do backend
from core.graph import app_graph

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Triagem Inteligente",
    page_icon="🏥",
    layout="centered"
)

st.title("🏥 Assistente de Triagem Hospitalar")
st.markdown("Insira os dados do paciente para iniciar a classificação de risco.")

# --- FUNÇÃO DE LIMPEZA DO GEMINI ---
def formatar_resposta(conteudo):
    """Extrai apenas o texto humano da resposta, ignorando o JSON estruturado do Gemini."""
    if isinstance(conteudo, str):
        return conteudo
    elif isinstance(conteudo, list):
        # Se for uma lista (JSON), pega apenas o valor dentro da chave "text"
        textos = [bloco.get("text", "") for bloco in conteudo if isinstance(bloco, dict) and "text" in bloco]
        return "\n".join(textos)
    return str(conteudo)

# --- 2. GERENCIAMENTO DE SESSÃO E MEMÓRIA ---
# Precisamos de um ID único para cada "paciente" (sessão) para o MemorySaver do LangGraph
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# O config é o que diz ao LangGraph qual "gaveta" de memória abrir
config = {"configurable": {"thread_id": st.session_state.thread_id}}

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 3. RENDERIZAÇÃO DO HISTÓRICO ---
for msg in st.session_state.messages:
    if isinstance(msg, HumanMessage):
        st.chat_message("user").write(msg.content)
    elif isinstance(msg, AIMessage) and msg.content:
        # Usa a função para limpar a mensagem antes de exibir
        st.chat_message("assistant").write(formatar_resposta(msg.content))

# --- 4. INTERAÇÃO DO USUÁRIO ---
user_input = st.chat_input("Ex: Paciente 45 anos, dor no peito, PA 140/90, FC 110...")

if user_input:
    # 4.1 Mostra a mensagem do enfermeiro na tela
    st.chat_message("user").write(user_input)
    st.session_state.messages.append(HumanMessage(content=user_input))
    
    # 4.2 Envia a mensagem para o LangGraph processar
    with st.spinner("Analisando protocolos clínicos..."):
        # O 'invoke' roda o grafo do START até o END (ou até pausar)
        # Passamos apenas a nova mensagem do usuário; o MemorySaver lembra do resto
        resultado_estado = app_graph.invoke(
            {"messages": [HumanMessage(content=user_input)]}, 
            config=config
        )
        
        # 4.3 Pega todas as mensagens geradas nesta rodada
        mensagens_geradas = resultado_estado["messages"]
        
        # Como o grafo pode ter rodado várias ferramentas em loop, 
        # a resposta final que queremos exibir para o usuário é a última mensagem do assistente.
        resposta_final = mensagens_geradas[-1]
        
        if isinstance(resposta_final, AIMessage) and resposta_final.content:
            # Limpa o texto da nova resposta antes de mostrar e salvar
            texto_limpo = formatar_resposta(resposta_final.content)
            
            st.chat_message("assistant").write(texto_limpo)
            # Salva já o texto limpo na memória para evitar acumular JSON na sessão
            st.session_state.messages.append(AIMessage(content=texto_limpo))