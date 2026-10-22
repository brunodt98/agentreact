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

    # Idade informada à calculadora (decide se o NEWS2 se aplica)
    idade: NotRequired[Optional[int]]

    # Últimos sinais vitais validados pela calculadora (frequencia_cardiaca, saturacao_o2, ...)
    sinais_vitais: NotRequired[dict]

    # Resultado do NEWS2 e sua classificação isolada
    escore_news2: NotRequired[Optional[int]]
    classificacao_news2: NotRequired[Optional[str]]

    # Pontos de cada parâmetro do NEWS2 (ex: {"frequencia_cardiaca": 2}); usado para colorir o painel
    pontos_news2: NotRequired[Optional[dict]]

    # Motivo de o NEWS2 não se aplicar (ex: paciente pediátrico); None quando se aplica
    escore_nao_aplicavel: NotRequired[Optional[str]]

    # Classificação final = a mais grave entre NEWS2 e sinais de alarme ("VERDE", "AMARELO", "VERMELHO")
    classificacao: NotRequired[Optional[str]]

    # True depois que o enfermeiro aprovou o acionamento da equipe de emergência
    emergencia_acionada: NotRequired[bool]
