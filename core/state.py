from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class TriageState(TypedDict):
    """
    Representa o estado (memória) do agente de triagem enquanto ele percorre o LangGraph.
    Todas as variáveis aqui viajam entre os nós do nosso fluxo.
    """
    # O histórico do chat. 
    # O 'add_messages' garante que novas mensagens sejam anexadas à lista, sem apagar o passado.
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Dados estruturados que o agente vai preenchendo ao longo do tempo
    sintomas_coletados: list[str]
    
    # Dicionário para guardar pressão, temperatura, batimentos, etc.
    sinais_vitais: dict
    
    # A classificação final de risco (ex: "VERDE", "AMARELO", "VERMELHO")
    escore_gravidade: str
    
    # Nossa trava de segurança do PRD (Human-in-the-loop)
    # Se for True, o fluxo para e pede aprovação do enfermeiro.
    precisa_humano: bool