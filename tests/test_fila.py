"""Fila do plantão montada a partir das triagens salvas (LLM falso, sem rede)."""
from datetime import timedelta

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from core.fila import listar_pacientes, marcar_atendido, pendencias
from core.graph import build_graph
from tests.test_graph import SINAIS, LLMRoteirizado, chamada

# NEWS2 = 0
NORMAIS = dict(SINAIS, frequencia_cardiaca=80, pressao_sistolica=120, frequencia_respiratoria=16, saturacao_o2=98)


def grafo_com(respostas):
    return build_graph(llm=LLMRoteirizado(respostas), checkpointer=MemorySaver())


def triar(grafo, thread_id, texto):
    grafo.invoke({"messages": [HumanMessage(content=texto)]}, {"configurable": {"thread_id": thread_id}})


def test_fila_ordena_por_gravidade_e_deixa_triagem_em_andamento_por_ultimo():
    grafo = grafo_com([
        chamada("calcular_escore_gravidade", NORMAIS), AIMessage(content="VERDE."),
        AIMessage(content="Qual a idade?"),
        chamada("calcular_escore_gravidade", SINAIS), AIMessage(content="VERMELHO."),
    ])
    triar(grafo, "verde", "Dor lombar leve")
    triar(grafo, "andamento", "Paciente com tontura")
    triar(grafo, "vermelho", "Falta de ar")

    fila = listar_pacientes(grafo)
    assert [p.thread_id for p in fila] == ["vermelho", "verde", "andamento"]
    assert fila[0].escore == 7 and fila[0].idade == 60
    assert fila[2].status == "Em triagem"
    assert fila[1].queixa == "Dor lombar leve"


def test_aprovacao_pendente_vira_pendencia_critica():
    grafo = grafo_com([chamada("acionar_equipe_emergencia", {"motivo": "Dor no peito"})])
    triar(grafo, "p1", "Dor no peito")

    [paciente] = listar_pacientes(grafo)
    assert paciente.status == "Aguardando aprovação"
    criticos = [texto for nivel, texto in pendencias([paciente]) if nivel == "critico"]
    assert criticos == [f"Paciente #{paciente.codigo} aguarda sua autorização para acionar a emergência"]


def test_vermelho_sem_equipe_acionada_e_critico():
    grafo = grafo_com([chamada("calcular_escore_gravidade", SINAIS), AIMessage(content="VERMELHO.")])
    triar(grafo, "p1", "Falta de ar")
    [paciente] = listar_pacientes(grafo)
    assert any(nivel == "critico" and "ainda não foi acionada" in texto for nivel, texto in pendencias([paciente]))


def test_marcar_atendido_tira_da_fila_e_nova_mensagem_traz_de_volta():
    grafo = grafo_com([
        chamada("calcular_escore_gravidade", NORMAIS), AIMessage(content="VERDE."),
        AIMessage(content="Anotado."),
    ])
    triar(grafo, "p1", "Dor lombar leve")
    marcar_atendido(grafo, "p1")
    assert listar_pacientes(grafo) == []

    triar(grafo, "p1", "Paciente voltou com piora da dor")
    assert [p.thread_id for p in listar_pacientes(grafo)] == ["p1"]


def test_espera_acima_da_meta_gera_alerta():
    grafo = grafo_com([chamada("calcular_escore_gravidade", NORMAIS), AIMessage(content="VERDE.")])
    triar(grafo, "p1", "Dor lombar leve")
    [paciente] = listar_pacientes(grafo)

    depois = paciente.chegada + timedelta(minutes=150)
    assert paciente.espera_min(depois) == 150 and paciente.fora_da_meta(depois)
    assert any(nivel == "alerta" and "acima da meta de 120 min" in texto for nivel, texto in pendencias([paciente], depois))
    assert not paciente.fora_da_meta(paciente.chegada + timedelta(minutes=30))


def test_pendencias_do_hospital():
    textos = [texto for _, texto in pendencias([])]
    assert any(t.startswith("Emergência sem leitos livres") for t in textos)
    assert any(t.startswith("Neurologia: Dra. Ana Silva está em cirurgia") for t in textos)
