"""Testes de fluxo do grafo com um LLM falso (roteirizado): sem rede e sem API key."""
import uuid

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from core.graph import build_graph


class LLMRoteirizado:
    """Devolve respostas pré-definidas em sequência e guarda o que recebeu."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def bind_tools(self, tools):
        return self

    def invoke(self, mensagens):
        self.chamadas.append(mensagens)
        return self.respostas.pop(0)


def chamada(nome, args, id_="c1"):
    return AIMessage(content="", tool_calls=[{"name": nome, "args": args, "id": id_, "type": "tool_call"}])


def novo_grafo(respostas):
    llm = LLMRoteirizado(respostas)
    grafo = build_graph(llm=llm, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    return grafo, llm, config


# NEWS2 = 7: FC 120 (2) + PAS 95 (2) + FR 22 (2) + SpO2 95 (1)
SINAIS = dict(idade=60, frequencia_cardiaca=120, pressao_sistolica=95, frequencia_respiratoria=22,
              saturacao_o2=95, oxigenio_suplementar=False, temperatura=37.0, nivel_consciencia="Alerta")


def test_news2_preenche_estado_estruturado():
    grafo, _, config = novo_grafo([
        chamada("calcular_escore_gravidade", SINAIS),
        AIMessage(content="Classificação VERMELHO."),
    ])
    estado = grafo.invoke({"messages": [HumanMessage(content="60 anos, FC 120, PAS 95, FR 22, SpO2 95% AA, 37C, alerta")]}, config)

    assert estado["escore_news2"] == 7
    assert estado["classificacao_news2"] == "VERMELHO"
    assert estado["classificacao"] == "VERMELHO"
    assert estado["idade"] == 60
    assert estado["sinais_vitais"]["frequencia_cardiaca"] == 120
    assert "idade" not in estado["sinais_vitais"]
    assert estado["pontos_news2"]["frequencia_cardiaca"] == 2


def test_red_flag_forca_vermelho_mesmo_com_news2_baixo():
    normais = dict(SINAIS, frequencia_cardiaca=80, pressao_sistolica=120, frequencia_respiratoria=16, saturacao_o2=98)
    grafo, llm, config = novo_grafo([
        chamada("calcular_escore_gravidade", normais),
        AIMessage(content="ok"),
    ])
    estado = grafo.invoke({"messages": [HumanMessage(content="Dor no peito irradiando, sinais normais")]}, config)

    assert estado["red_flags"] == ["Dor torácica"]
    assert estado["classificacao_news2"] == "VERDE"
    assert estado["classificacao"] == "VERMELHO"  # nunca rebaixa
    # O LLM recebeu o alerta no system prompt
    assert "SINAIS DE ALARME DETECTADOS" in llm.chamadas[0][0].content


def test_acao_sensivel_pausa_e_executa_apos_aprovacao():
    grafo, _, config = novo_grafo([
        chamada("acionar_equipe_emergencia", {"motivo": "Dor no peito", "especialidade": "Cardiologia"}),
        AIMessage(content="Equipe acionada."),
    ])
    grafo.invoke({"messages": [HumanMessage(content="Dor no peito")]}, config)

    snapshot = grafo.get_state(config)
    assert snapshot.next == ("aprovacao_humana",)
    pedido = snapshot.tasks[0].interrupts[0].value
    assert pedido["acoes"][0]["ferramenta"] == "acionar_equipe_emergencia"

    estado = grafo.invoke(Command(resume={"aprovado": True}), config)
    assert estado["emergencia_acionada"] is True
    tool_msgs = [m for m in estado["messages"] if isinstance(m, ToolMessage)]
    assert "Equipe de emergência acionada" in tool_msgs[-1].content


def test_acao_rejeitada_nao_executa():
    grafo, _, config = novo_grafo([
        chamada("acionar_equipe_emergencia", {"motivo": "Dor no peito"}),
        AIMessage(content="Entendido, não acionei."),
    ])
    grafo.invoke({"messages": [HumanMessage(content="Dor no peito")]}, config)
    estado = grafo.invoke(Command(resume={"aprovado": False, "observacao": "Já está com o médico"}), config)

    assert not estado.get("emergencia_acionada")
    ultima_tool = [m for m in estado["messages"] if isinstance(m, ToolMessage)][-1]
    assert "rejeitada" in ultima_tool.content and "Já está com o médico" in ultima_tool.content


def test_valor_invalido_volta_como_erro_para_o_llm():
    grafo, _, config = novo_grafo([
        chamada("calcular_escore_gravidade", dict(SINAIS, frequencia_cardiaca=900)),
        AIMessage(content="Confirme a FC, por favor."),
    ])
    estado = grafo.invoke({"messages": [HumanMessage(content="FC 900")]}, config)

    assert estado.get("escore_news2") is None
    erro = [m for m in estado["messages"] if isinstance(m, ToolMessage)][-1]
    assert erro.status == "error"


def test_paciente_pediatrico_nao_recebe_escore_adulto():
    grafo, llm, config = novo_grafo([
        chamada("calcular_escore_gravidade", dict(SINAIS, idade=7)),
        AIMessage(content="NEWS2 não se aplica; seguir protocolo pediátrico."),
    ])
    estado = grafo.invoke({"messages": [HumanMessage(content="Criança de 7 anos, FC 120")]}, config)

    assert estado["idade"] == 7
    assert estado.get("escore_news2") is None
    assert estado.get("classificacao") is None
    assert "Paciente pediátrico" in estado["escore_nao_aplicavel"]
    # O LLM foi avisado no system prompt da segunda chamada
    assert "NEWS2 NÃO SE APLICA" in llm.chamadas[1][0].content


def test_idade_corrigida_para_crianca_descarta_escore_adulto():
    grafo, _, config = novo_grafo([
        chamada("calcular_escore_gravidade", SINAIS, id_="c1"),
        AIMessage(content="Classificação VERMELHO."),
        chamada("calcular_escore_gravidade", dict(SINAIS, idade=10), id_="c2"),
        AIMessage(content="Corrigido: paciente pediátrico."),
    ])
    grafo.invoke({"messages": [HumanMessage(content="60 anos, FC 120...")]}, config)
    estado = grafo.invoke({"messages": [HumanMessage(content="Correção: são 10 anos")]}, config)

    assert estado["escore_news2"] is None and estado["classificacao_news2"] is None
    assert estado["classificacao"] is None
    assert estado["escore_nao_aplicavel"]
