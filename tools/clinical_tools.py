from typing import Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from utils.text import normalizar

# Ordem de gravidade usada para combinar classificações (MEWS x sinais de alarme)
NIVEIS_GRAVIDADE = ["VERDE", "AMARELO", "VERMELHO"]

NivelConsciencia = Literal["Alerta", "Voz", "Dor", "Inconsciente"]

# Aceita as variações mais comuns que o LLM ou o enfermeiro podem enviar (escala AVPU)
_MAPA_CONSCIENCIA = {
    "a": "Alerta", "alerta": "Alerta", "alert": "Alerta", "lucido": "Alerta", "orientado": "Alerta",
    "v": "Voz", "voz": "Voz", "verbal": "Voz", "responde a voz": "Voz",
    "p": "Dor", "dor": "Dor", "pain": "Dor", "responde a dor": "Dor",
    "u": "Inconsciente", "inconsciente": "Inconsciente", "unresponsive": "Inconsciente",
    "nao responde": "Inconsciente", "arresponsivo": "Inconsciente",
}

CAMPOS_OBRIGATORIOS = {
    "frequencia_cardiaca": "frequência cardíaca (bpm)",
    "pressao_sistolica": "pressão arterial sistólica (mmHg)",
    "frequencia_respiratoria": "frequência respiratória (irpm)",
    "temperatura": "temperatura (°C)",
    "nivel_consciencia": "nível de consciência (AVPU)",
}


def pior_classificacao(*classificacoes: Optional[str]) -> Optional[str]:
    """Retorna a classificação mais grave entre as informadas (ignorando None)."""
    validas = [c for c in classificacoes if c in NIVEIS_GRAVIDADE]
    if not validas:
        return None
    return max(validas, key=NIVEIS_GRAVIDADE.index)


# --- 1. SCHEMAS DE VALIDAÇÃO (PYDANTIC) ---

class SinaisVitaisInput(BaseModel):
    """
    Esquema de entrada da calculadora de risco.
    Todos os campos são opcionais de propósito: se algum faltar, a ferramenta devolve
    a lista do que falta em vez de deixar o LLM inventar um valor para conseguir chamá-la.
    As faixas (ge/le) barram valores fisiologicamente impossíveis (erros de digitação).
    """
    frequencia_cardiaca: Optional[int] = Field(
        default=None, ge=20, le=250,
        description="Frequência cardíaca em bpm. Omita se não foi informada."
    )
    pressao_sistolica: Optional[int] = Field(
        default=None, ge=40, le=300,
        description="Apenas o valor sistólico da pressão arterial em mmHg. Ex: se for 120/80, informe 120. Omita se não foi informada."
    )
    frequencia_respiratoria: Optional[int] = Field(
        default=None, ge=4, le=70,
        description="Frequência respiratória em irpm. Omita se não foi informada."
    )
    temperatura: Optional[float] = Field(
        default=None, ge=30.0, le=45.0,
        description="Temperatura corporal em graus Celsius. Ex: 37.5. Omita se não foi informada."
    )
    nivel_consciencia: Optional[NivelConsciencia] = Field(
        default=None,
        description="Estado mental (escala AVPU): 'Alerta', 'Voz' (responde à voz), 'Dor' (responde à dor) ou 'Inconsciente'. Omita se não foi informado."
    )

    @field_validator("nivel_consciencia", mode="before")
    @classmethod
    def normalizar_consciencia(cls, valor):
        if valor is None or not isinstance(valor, str):
            return valor
        return _MAPA_CONSCIENCIA.get(normalizar(valor).strip(" ."), valor)


# --- 2. LÓGICA PURA DO MEWS (testável sem LLM) ---

def _pontos_fc(fc: int) -> int:
    if fc < 40: return 2
    if fc <= 50: return 1
    if fc <= 100: return 0
    if fc <= 110: return 1
    if fc <= 129: return 2
    return 3


def _pontos_pas(pas: int) -> int:
    if pas <= 70: return 3
    if pas <= 80: return 2
    if pas <= 100: return 1
    if pas <= 199: return 0
    return 2


def _pontos_fr(fr: int) -> int:
    if fr < 9: return 2
    if fr <= 14: return 0
    if fr <= 20: return 1
    if fr <= 29: return 2
    return 3


def _pontos_temp(temp: float) -> int:
    if temp < 35.0: return 2
    if temp < 38.5: return 0
    return 2


_PONTOS_AVPU = {"Alerta": 0, "Voz": 1, "Dor": 2, "Inconsciente": 3}


def calcular_mews(sinais: SinaisVitaisInput) -> dict:
    """
    Calcula o MEWS (Modified Early Warning Score, Subbe et al. 2001).

    Regras de classificação:
    - VERMELHO: escore total >= 5 ou paciente inconsciente.
    - AMARELO: escore total 3-4, ou qualquer parâmetro isolado com 3 pontos.
    - VERDE: demais casos.
    """
    dados = sinais.model_dump()
    faltando = [rotulo for campo, rotulo in CAMPOS_OBRIGATORIOS.items() if dados[campo] is None]
    if faltando:
        return {"completo": False, "faltando": faltando, "sinais_vitais": {k: v for k, v in dados.items() if v is not None}}

    detalhe = {
        "frequencia_cardiaca": _pontos_fc(sinais.frequencia_cardiaca),
        "pressao_sistolica": _pontos_pas(sinais.pressao_sistolica),
        "frequencia_respiratoria": _pontos_fr(sinais.frequencia_respiratoria),
        "temperatura": _pontos_temp(sinais.temperatura),
        "nivel_consciencia": _PONTOS_AVPU[sinais.nivel_consciencia],
    }
    score = sum(detalhe.values())

    if score >= 5 or sinais.nivel_consciencia == "Inconsciente":
        classificacao = "VERMELHO"
    elif score >= 3 or max(detalhe.values()) == 3:
        classificacao = "AMARELO"
    else:
        classificacao = "VERDE"

    return {
        "completo": True,
        "escore": score,
        "classificacao": classificacao,
        "pontos_por_parametro": detalhe,
        "sinais_vitais": dados,
    }


_TEXTO_CLASSIFICACAO = {
    "VERMELHO": "VERMELHO (Emergência). Risco altíssimo. Requer Sala de Emergência/UTI imediata.",
    "AMARELO": "AMARELO (Urgência). Risco moderado a alto. Avaliação médica rápida necessária.",
    "VERDE": "VERDE (Pouco urgente). Risco baixo. Fluxo padrão de atendimento.",
}


# --- 3. FERRAMENTA EXPOSTA AO AGENTE ---

@tool("calcular_escore_gravidade", args_schema=SinaisVitaisInput, response_format="content_and_artifact")
def calcular_escore_gravidade(
    frequencia_cardiaca: Optional[int] = None,
    pressao_sistolica: Optional[int] = None,
    frequencia_respiratoria: Optional[int] = None,
    temperatura: Optional[float] = None,
    nivel_consciencia: Optional[str] = None,
) -> tuple[str, dict]:
    """
    Calcula o escore de gravidade clínica do paciente pelo protocolo MEWS.
    Envie SOMENTE os sinais vitais informados explicitamente pelo enfermeiro; omita os demais.
    Se faltar algum dado, a ferramenta responde quais sinais ainda precisam ser coletados.
    """
    sinais = SinaisVitaisInput(
        frequencia_cardiaca=frequencia_cardiaca,
        pressao_sistolica=pressao_sistolica,
        frequencia_respiratoria=frequencia_respiratoria,
        temperatura=temperatura,
        nivel_consciencia=nivel_consciencia,
    )
    resultado = calcular_mews(sinais)

    if not resultado["completo"]:
        texto = (
            "DADOS INSUFICIENTES: o escore NÃO foi calculado. Pergunte ao enfermeiro: "
            + "; ".join(resultado["faltando"]) + ". Não estime valores."
        )
        return texto, resultado

    prefixo = "ALERTA: " if resultado["classificacao"] == "VERMELHO" else ""
    texto = f"{prefixo}Score MEWS={resultado['escore']}. Classificação: {_TEXTO_CLASSIFICACAO[resultado['classificacao']]}"
    return texto, resultado
