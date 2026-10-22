from typing import Annotated, NotRequired, Optional, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class TriageState(TypedDict):
    """
    Representa o estado (memória) do agente de triagem enquanto ele percorre o LangGraph.
    Todas as variáveis aqui viajam entre os nós do nosso fluxo.
    Os campos estruturados são preenchidos por código Python (nós red_flags e registrar_resultados),
    nunca por texto livre do LLM.
    """
    # O histórico do chat.
    # O 'add_messages' garante que novas mensagens sejam anexadas à lista, sem apagar o passado.
    messages: Annotated[list[BaseMessage], add_messages]

    # Sintomas de Risco Imediato detectados por regra (ex: "Dor torácica")
    red_flags: NotRequired[list[str]]

    # Últimos sinais vitais validados pela calculadora (frequencia_cardiaca, temperatura, ...)
    sinais_vitais: NotRequired[dict]

    # Resultado do MEWS e sua classificação isolada
    escore_mews: NotRequired[Optional[int]]
    classificacao_mews: NotRequired[Optional[str]]

    # Classificação final = a mais grave entre MEWS e sinais de alarme ("VERDE", "AMARELO", "VERMELHO")
    classificacao: NotRequired[Optional[str]]

    # True depois que o enfermeiro aprovou o acionamento da equipe de emergência
    emergencia_acionada: NotRequired[bool]
