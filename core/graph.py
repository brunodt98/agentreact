import os
from functools import lru_cache
from typing import Literal

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from core.state import TriageState
from core.prompts import SYSTEM_PROMPT, montar_contexto_estado
from core.red_flags import detectar_red_flags
from tools import ALL_TOOLS, FERRAMENTAS_SENSIVEIS
from tools.clinical_tools import pior_classificacao
from utils.logger import logger
from utils.text import conteudo_para_texto

# --- 1. MODELO ---

@lru_cache(maxsize=1)
def _llm_padrao():
    """
    Cria o Gemini sob demanda (e uma única vez). Importar este módulo não exige
    GOOGLE_API_KEY, o que permite rodar os testes sem chave e sem rede.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    modelo = os.getenv("TRIAGEM_MODELO", "gemini-2.5-flash")
    # temperature=0.0 para respostas o mais determinísticas possível
    return ChatGoogleGenerativeAI(model=modelo, temperature=0.0)


# --- 2. NÓS DO GRAFO ---

def red_flags_node(state: TriageState):
    """
    Varre a última mensagem do enfermeiro em busca de Sintomas de Risco Imediato.
    É regra em Python, não depende do LLM: se achar algo, a classificação vira VERMELHO.
    """
    ultima = state["messages"][-1] if state["messages"] else None
    if not isinstance(ultima, HumanMessage):
        return {}

    novas = detectar_red_flags(conteudo_para_texto(ultima.content))
    if not novas:
        return {}

    acumuladas = list(dict.fromkeys((state.get("red_flags") or []) + novas))
    logger.warning("Sinais de alarme detectados: %s", novas)
    return {
        "red_flags": acumuladas,
        "classificacao": pior_classificacao("VERMELHO", state.get("classificacao_news2")),
    }


def registrar_resultados_node(state: TriageState):
    """
    Lê os resultados estruturados (artifacts) das ferramentas que acabaram de rodar
    e atualiza o estado. Assim o painel e as regras usam números, não texto do LLM.
    """
    atualizacao = {}
    for msg in reversed(state["messages"]):
        if not isinstance(msg, ToolMessage):
            break  # chegamos no AIMessage que pediu as ferramentas
        if getattr(msg, "status", "success") == "error":
            continue

        if msg.name == "calcular_escore_gravidade" and isinstance(msg.artifact, dict):
            resultado = msg.artifact
            sinais = dict(resultado.get("sinais_vitais", {}))
            if sinais.get("idade") is not None:
                atualizacao["idade"] = sinais.pop("idade")
            atualizacao["sinais_vitais"] = {**(state.get("sinais_vitais") or {}), **sinais}

            if resultado.get("status") == "calculado":
                atualizacao["escore_news2"] = resultado["escore"]
                atualizacao["classificacao_news2"] = resultado["classificacao"]
                atualizacao["pontos_news2"] = resultado["pontos_por_parametro"]
                atualizacao["escore_nao_aplicavel"] = None
                logger.info("NEWS2=%s (%s)", resultado["escore"], resultado["classificacao"])
            elif resultado.get("status") == "nao_aplicavel":
                # Um escore adulto anterior (ex: idade corrigida) deixa de valer
                atualizacao["escore_news2"] = None
                atualizacao["classificacao_news2"] = None
                atualizacao["pontos_news2"] = None
                atualizacao["escore_nao_aplicavel"] = resultado["motivo"]
                logger.info("NEWS2 não aplicável: %s", resultado["motivo"])

        elif msg.name == "acionar_equipe_emergencia":
            atualizacao["emergencia_acionada"] = True

    if "classificacao_news2" in atualizacao:
        alarme = "VERMELHO" if state.get("red_flags") else None
        atualizacao["classificacao"] = pior_classificacao(alarme, atualizacao["classificacao_news2"])
    return atualizacao


def aprovacao_humana_node(state: TriageState) -> Command[Literal["tools", "agent"]]:
    """
    Human-in-the-loop: pausa o grafo antes de executar ações sensíveis e espera o enfermeiro.
    O app retoma com Command(resume={"aprovado": bool, "observacao": str}).
    """
    ultima: AIMessage = state["messages"][-1]
    acoes = [
        {"ferramenta": tc["name"], "argumentos": tc["args"]}
        for tc in ultima.tool_calls if tc["name"] in FERRAMENTAS_SENSIVEIS
    ]

    decisao = interrupt({"tipo": "aprovacao", "acoes": acoes})

    if isinstance(decisao, dict) and decisao.get("aprovado"):
        logger.info("Enfermeiro APROVOU: %s", acoes)
        return Command(goto="tools")

    observacao = (decisao or {}).get("observacao") if isinstance(decisao, dict) else None
    logger.info("Enfermeiro REJEITOU: %s | obs=%s", acoes, observacao)
    texto = "Ação NÃO executada: rejeitada pelo enfermeiro."
    if observacao:
        texto += f" Observação do enfermeiro: {observacao}"
    # Toda tool_call precisa de uma resposta, senão o próximo turno do LLM é inválido
    respostas = [
        ToolMessage(content=texto, tool_call_id=tc["id"], name=tc["name"])
        for tc in ultima.tool_calls
    ]
    return Command(goto="agent", update={"messages": respostas})


def rotear_apos_agente(state: TriageState) -> str:
    """Decide o próximo passo: responder (END), rodar ferramentas, ou pedir aprovação antes."""
    ultima = state["messages"][-1]
    if not isinstance(ultima, AIMessage) or not ultima.tool_calls:
        return END
    if any(tc["name"] in FERRAMENTAS_SENSIVEIS for tc in ultima.tool_calls):
        return "aprovacao_humana"
    return "tools"


# --- 3. CONSTRUÇÃO DO GRAFO (WORKFLOW) ---

def build_graph(llm=None, checkpointer=None):
    """
    Monta e compila o grafo.
    - llm: modelo de chat com suporte a bind_tools (padrão: Gemini). Testes injetam um modelo falso.
    - checkpointer: memória do grafo; obrigatório para o human-in-the-loop (interrupt).
    """

    def agent_node(state: TriageState):
        """Nó principal onde o LLM avalia o estado atual e decide a próxima ação."""
        modelo = (llm or _llm_padrao()).bind_tools(ALL_TOOLS)
        # O system prompt não é salvo no histórico: é remontado a cada chamada,
        # já com o estado estruturado mais recente.
        system = SystemMessage(content=SYSTEM_PROMPT + "\n\n" + montar_contexto_estado(state))
        response = modelo.invoke([system] + state["messages"])
        return {"messages": [response]}

    workflow = StateGraph(TriageState)

    workflow.add_node("red_flags", red_flags_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("aprovacao_humana", aprovacao_humana_node)
    # ToolNode roda a função Python pedida pelo LLM; erros de validação (Pydantic)
    # voltam como mensagem para o LLM corrigir, em vez de derrubar o app.
    workflow.add_node("tools", ToolNode(ALL_TOOLS))
    workflow.add_node("registrar_resultados", registrar_resultados_node)

    workflow.add_edge(START, "red_flags")
    workflow.add_edge("red_flags", "agent")
    workflow.add_conditional_edges("agent", rotear_apos_agente, ["tools", "aprovacao_humana", END])
    workflow.add_edge("tools", "registrar_resultados")
    workflow.add_edge("registrar_resultados", "agent")

    return workflow.compile(checkpointer=checkpointer)


# --- 4. INSTÂNCIAS ---

# Usada pelo Streamlit: MemorySaver guarda o estado por thread_id (um por paciente)
# e permite pausar/retomar no human-in-the-loop.
app_graph = build_graph(checkpointer=MemorySaver())

# Usada pelo LangGraph Studio/Server (langgraph.json), que fornece a própria persistência.
graph = build_graph()
