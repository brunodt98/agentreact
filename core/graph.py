from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage

# 1. Substitua o import da OpenAI pelo do Google
from langchain_google_genai import ChatGoogleGenerativeAI

from core.state import TriageState
from core.prompts import SYSTEM_PROMPT
from tools import ALL_TOOLS

# 2. Inicialize o modelo Gemini 1.5 Flash (gratuito e super rápido)
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)


# Acoplamos as ferramentas ao modelo para que ele saiba o que pode chamar
llm_with_tools = llm.bind_tools(ALL_TOOLS)

# --- 2. DEFINIÇÃO DOS NÓS DO GRAFO ---

def agent_node(state: TriageState):
    """
    Nó principal onde o LLM avalia o estado atual e decide a próxima ação.
    """
    messages = state["messages"]
    
    # Garantimos que o System Prompt seja sempre a primeira instrução lida pelo modelo
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        
    # O modelo lê o histórico e decide se responde ao usuário ou chama uma ferramenta
    response = llm_with_tools.invoke(messages)
    
    # Retorna a nova mensagem para o LangGraph anexar ao state["messages"]
    return {"messages": [response]}

# O ToolNode já é um nó pré-construído pelo LangGraph que roda a função Python correta 
# baseada na requisição do LLM e devolve a "Observação" para o grafo.
tool_node = ToolNode(ALL_TOOLS)

# --- 3. CONSTRUÇÃO DO GRAFO (WORKFLOW) ---

workflow = StateGraph(TriageState)

# Adicionamos os nós
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)

# Desenhamos o fluxo (Arestas)
workflow.add_edge(START, "agent")

# A tools_condition verifica automaticamente a última mensagem do "agent":
# - Se o LLM pediu para usar uma ferramenta, o fluxo vai para o nó "tools".
# - Se o LLM deu a resposta em texto normal, o fluxo vai para "END".
workflow.add_conditional_edges("agent", tools_condition)

# Depois que uma ferramenta roda, o fluxo obrigatoriamente volta pro agente avaliar o resultado
workflow.add_edge("tools", "agent")

# --- 4. COMPILAÇÃO E MEMÓRIA (HUMAN-IN-THE-LOOP) ---

# O MemorySaver guarda o estado do grafo a cada passo. 
# Ele é fundamental para a interface no Streamlit, pois permite pausar e retomar a conversa.
memory = MemorySaver()

# Compilamos o grafo com a memória habilitada. 
# O parâmetro interrupt_before=["tools"] pode ser usado no futuro para forçar 
# uma pausa antes de rodar qualquer ferramenta crítica.
app_graph = workflow.compile(checkpointer=memory)