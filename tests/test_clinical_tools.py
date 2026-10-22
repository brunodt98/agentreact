import pytest
from pydantic import ValidationError

from tools.clinical_tools import SinaisVitaisInput, calcular_escore_gravidade, calcular_mews, pior_classificacao

NORMAL = dict(frequencia_cardiaca=80, pressao_sistolica=120, frequencia_respiratoria=12,
              temperatura=36.5, nivel_consciencia="Alerta")


def mews(**alteracoes):
    return calcular_mews(SinaisVitaisInput(**{**NORMAL, **alteracoes}))


def test_paciente_normal_e_verde():
    r = mews()
    assert r["completo"] and r["escore"] == 0 and r["classificacao"] == "VERDE"


@pytest.mark.parametrize("campo,valor,pontos", [
    ("frequencia_cardiaca", 39, 2), ("frequencia_cardiaca", 45, 1), ("frequencia_cardiaca", 105, 1),
    ("frequencia_cardiaca", 120, 2), ("frequencia_cardiaca", 130, 3),
    ("pressao_sistolica", 70, 3), ("pressao_sistolica", 75, 2), ("pressao_sistolica", 95, 1),
    ("pressao_sistolica", 199, 0), ("pressao_sistolica", 200, 2),
    ("frequencia_respiratoria", 8, 2), ("frequencia_respiratoria", 14, 0), ("frequencia_respiratoria", 15, 1),
    ("frequencia_respiratoria", 25, 2), ("frequencia_respiratoria", 30, 3),
    ("temperatura", 34.9, 2), ("temperatura", 38.4, 0), ("temperatura", 38.5, 2),
    ("nivel_consciencia", "Voz", 1), ("nivel_consciencia", "Dor", 2), ("nivel_consciencia", "Inconsciente", 3),
])
def test_pontuacao_por_parametro_segue_mews(campo, valor, pontos):
    assert mews(**{campo: valor})["pontos_por_parametro"][campo] == pontos


def test_score_alto_e_vermelho():
    r = mews(frequencia_cardiaca=120, pressao_sistolica=85, frequencia_respiratoria=25)
    assert r["escore"] == 5 and r["classificacao"] == "VERMELHO"


def test_inconsciente_e_sempre_vermelho():
    assert mews(nivel_consciencia="Inconsciente")["classificacao"] == "VERMELHO"


def test_parametro_isolado_com_3_pontos_e_no_minimo_amarelo():
    r = mews(frequencia_cardiaca=135)
    assert r["escore"] == 3 and r["classificacao"] == "AMARELO"


def test_dados_faltando_nao_calcula():
    r = calcular_mews(SinaisVitaisInput(frequencia_cardiaca=80, temperatura=37.0))
    assert not r["completo"]
    assert len(r["faltando"]) == 3


@pytest.mark.parametrize("entrada", ["alerta", "A", "Alerta.", "lúcido"])
def test_normaliza_consciencia(entrada):
    assert SinaisVitaisInput(nivel_consciencia=entrada).nivel_consciencia == "Alerta"


@pytest.mark.parametrize("campo,valor", [
    ("frequencia_cardiaca", 900), ("frequencia_cardiaca", 0), ("temperatura", 60.0), ("nivel_consciencia", "confuso"),
])
def test_rejeita_valores_impossiveis(campo, valor):
    with pytest.raises(ValidationError):
        SinaisVitaisInput(**{campo: valor})


def test_tool_devolve_texto_e_artifact():
    chamada = {"name": "calcular_escore_gravidade", "args": NORMAL, "id": "1", "type": "tool_call"}
    msg = calcular_escore_gravidade.invoke(chamada)
    assert "VERDE" in msg.content
    assert msg.artifact["escore"] == 0


def test_tool_com_dados_faltando_pede_coleta():
    chamada = {"name": "calcular_escore_gravidade", "args": {"frequencia_cardiaca": 80}, "id": "1", "type": "tool_call"}
    msg = calcular_escore_gravidade.invoke(chamada)
    assert "DADOS INSUFICIENTES" in msg.content


def test_pior_classificacao():
    assert pior_classificacao("VERDE", "VERMELHO", None) == "VERMELHO"
    assert pior_classificacao(None, "AMARELO") == "AMARELO"
    assert pior_classificacao(None) is None
