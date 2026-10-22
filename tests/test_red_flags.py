import pytest

from core.red_flags import detectar_red_flags


@pytest.mark.parametrize("texto,esperado", [
    ("Paciente 45 anos, dor no peito irradiando para o braço", "Dor torácica"),
    ("Refere DOR TORÁCICA há 2h", "Dor torácica"),
    ("Não consegue respirar, lábios roxos", "Dificuldade respiratória grave"),
    ("Teve um desmaio na recepção", "Alteração/perda de consciência"),
    ("Sangramento ativo em membro inferior", "Sangramento ativo massivo"),
    ("Familiar notou boca torta e fala enrolada", "Suspeita de AVC"),
])
def test_detecta_sinais_de_alarme(texto, esperado):
    assert esperado in detectar_red_flags(texto)


@pytest.mark.parametrize("texto", [
    "Nega dor no peito",
    "Paciente sem dor torácica, apenas tosse",
    "Dor de cabeça leve há 2 dias, PA 120/80",
    "Não houve desmaio",
])
def test_ignora_sintomas_negados_ou_ausentes(texto):
    assert detectar_red_flags(texto) == []


def test_negacao_nao_vaza_para_outra_oracao():
    # "sem febre" não pode anular a dor no peito que vem depois
    assert "Dor torácica" in detectar_red_flags("Sem febre, com dor no peito")


def test_multiplas_categorias_sem_duplicatas():
    flags = detectar_red_flags("Dor no peito, dor torácica intensa e desmaio")
    assert flags == ["Dor torácica", "Alteração/perda de consciência"]
