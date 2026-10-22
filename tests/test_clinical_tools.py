import pytest
from pydantic import ValidationError

from tools.clinical_tools import SinaisVitaisInput, calcular_escore_gravidade, calcular_news2, pior_classificacao

NORMAL = dict(idade=40, frequencia_cardiaca=80, pressao_sistolica=120, frequencia_respiratoria=16,
              saturacao_o2=98, oxigenio_suplementar=False, temperatura=36.8, nivel_consciencia="Alerta")


def news2(**alteracoes):
    return calcular_news2(SinaisVitaisInput(**{**NORMAL, **alteracoes}))


def test_paciente_normal_e_verde():
    r = news2()
    assert r["status"] == "calculado" and r["escore"] == 0 and r["classificacao"] == "VERDE"


@pytest.mark.parametrize("campo,valor,pontos", [
    ("frequencia_respiratoria", 8, 3), ("frequencia_respiratoria", 9, 1), ("frequencia_respiratoria", 11, 1),
    ("frequencia_respiratoria", 12, 0), ("frequencia_respiratoria", 20, 0), ("frequencia_respiratoria", 21, 2),
    ("frequencia_respiratoria", 24, 2), ("frequencia_respiratoria", 25, 3),
    ("saturacao_o2", 91, 3), ("saturacao_o2", 92, 2), ("saturacao_o2", 93, 2), ("saturacao_o2", 94, 1),
    ("saturacao_o2", 95, 1), ("saturacao_o2", 96, 0),
    ("oxigenio_suplementar", True, 2), ("oxigenio_suplementar", False, 0),
    ("pressao_sistolica", 90, 3), ("pressao_sistolica", 91, 2), ("pressao_sistolica", 100, 2),
    ("pressao_sistolica", 101, 1), ("pressao_sistolica", 110, 1), ("pressao_sistolica", 111, 0),
    ("pressao_sistolica", 219, 0), ("pressao_sistolica", 220, 3),
    ("frequencia_cardiaca", 40, 3), ("frequencia_cardiaca", 41, 1), ("frequencia_cardiaca", 50, 1),
    ("frequencia_cardiaca", 51, 0), ("frequencia_cardiaca", 90, 0), ("frequencia_cardiaca", 91, 1),
    ("frequencia_cardiaca", 110, 1), ("frequencia_cardiaca", 111, 2), ("frequencia_cardiaca", 130, 2),
    ("frequencia_cardiaca", 131, 3),
    ("temperatura", 35.0, 3), ("temperatura", 35.1, 1), ("temperatura", 36.0, 1), ("temperatura", 36.1, 0),
    ("temperatura", 38.0, 0), ("temperatura", 38.1, 1), ("temperatura", 39.0, 1), ("temperatura", 39.1, 2),
    ("nivel_consciencia", "Confuso", 3), ("nivel_consciencia", "Voz", 3), ("nivel_consciencia", "Dor", 3),
    ("nivel_consciencia", "Inconsciente", 3),
])
def test_pontuacao_por_parametro_segue_news2(campo, valor, pontos):
    assert news2(**{campo: valor})["pontos_por_parametro"][campo] == pontos


def test_score_7_e_vermelho():
    # FC 120 (2) + PAS 95 (2) + FR 22 (2) + SpO2 95 (1) = 7
    r = news2(frequencia_cardiaca=120, pressao_sistolica=95, frequencia_respiratoria=22, saturacao_o2=95)
    assert r["escore"] == 7 and r["classificacao"] == "VERMELHO"


def test_score_5_e_amarelo():
    # FC 120 (2) + FR 22 (2) + SpO2 95 (1) = 5
    r = news2(frequencia_cardiaca=120, frequencia_respiratoria=22, saturacao_o2=95)
    assert r["escore"] == 5 and r["classificacao"] == "AMARELO"


def test_score_baixo_sem_parametro_extremo_e_verde():
    # FC 100 (1) + SpO2 95 (1) + Temp 38.5 (1) = 3
    r = news2(frequencia_cardiaca=100, saturacao_o2=95, temperatura=38.5)
    assert r["escore"] == 3 and r["classificacao"] == "VERDE"


def test_parametro_isolado_com_3_pontos_e_no_minimo_amarelo():
    r = news2(saturacao_o2=90)
    assert r["escore"] == 3 and r["classificacao"] == "AMARELO"


def test_inconsciente_e_sempre_vermelho():
    assert news2(nivel_consciencia="Inconsciente")["classificacao"] == "VERMELHO"


def test_oxigenio_soma_pontos():
    assert news2(oxigenio_suplementar=True)["escore"] == 2


def test_dados_faltando_nao_calcula():
    r = calcular_news2(SinaisVitaisInput(idade=40, frequencia_cardiaca=80, temperatura=37.0))
    assert r["status"] == "incompleto"
    assert len(r["faltando"]) == 5


def test_idade_e_obrigatoria():
    sem_idade = {k: v for k, v in NORMAL.items() if k != "idade"}
    r = calcular_news2(SinaisVitaisInput(**sem_idade))
    assert r["status"] == "incompleto" and r["faltando"] == ["idade (anos)"]


@pytest.mark.parametrize("idade", [0, 8, 15])
def test_menor_de_16_nao_aplica_news2(idade):
    r = news2(idade=idade, frequencia_cardiaca=130)
    assert r["status"] == "nao_aplicavel"
    assert "escore" not in r and "classificacao" not in r


def test_menor_de_16_nao_aplica_mesmo_sem_os_demais_sinais():
    r = calcular_news2(SinaisVitaisInput(idade=5))
    assert r["status"] == "nao_aplicavel"


def test_16_anos_ja_calcula():
    assert news2(idade=16)["status"] == "calculado"


@pytest.mark.parametrize("entrada,esperado", [
    ("alerta", "Alerta"), ("A", "Alerta"), ("Alerta.", "Alerta"), ("lúcido", "Alerta"),
    ("confuso", "Confuso"), ("desorientado", "Confuso"), ("C", "Confuso"),
])
def test_normaliza_consciencia(entrada, esperado):
    assert SinaisVitaisInput(nivel_consciencia=entrada).nivel_consciencia == esperado


@pytest.mark.parametrize("campo,valor", [
    ("frequencia_cardiaca", 900), ("frequencia_cardiaca", 0), ("temperatura", 60.0),
    ("saturacao_o2", 120), ("idade", -1), ("idade", 150), ("nivel_consciencia", "sonolento"),
])
def test_rejeita_valores_impossiveis(campo, valor):
    with pytest.raises(ValidationError):
        SinaisVitaisInput(**{campo: valor})


def test_tool_devolve_texto_e_artifact():
    chamada = {"name": "calcular_escore_gravidade", "args": NORMAL, "id": "1", "type": "tool_call"}
    msg = calcular_escore_gravidade.invoke(chamada)
    assert "NEWS2=0" in msg.content and "VERDE" in msg.content
    assert msg.artifact["escore"] == 0


def test_tool_com_dados_faltando_pede_coleta():
    chamada = {"name": "calcular_escore_gravidade", "args": {"frequencia_cardiaca": 80}, "id": "1", "type": "tool_call"}
    msg = calcular_escore_gravidade.invoke(chamada)
    assert "DADOS INSUFICIENTES" in msg.content and "idade" in msg.content


def test_tool_pediatrica_orienta_protocolo():
    chamada = {"name": "calcular_escore_gravidade", "args": {"idade": 6}, "id": "1", "type": "tool_call"}
    msg = calcular_escore_gravidade.invoke(chamada)
    assert "NÃO APLICÁVEL" in msg.content and "pediátrico" in msg.content


def test_pior_classificacao():
    assert pior_classificacao("VERDE", "VERMELHO", None) == "VERMELHO"
    assert pior_classificacao(None, "AMARELO") == "AMARELO"
    assert pior_classificacao(None) is None
