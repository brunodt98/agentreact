from typing import Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from utils.text import normalizar

# Ordem de gravidade usada para combinar classificações (NEWS2 x sinais de alarme)
NIVEIS_GRAVIDADE = ["VERDE", "AMARELO", "VERMELHO"]

# O NEWS2 não é validado para menores de 16 anos (Royal College of Physicians, 2017)
IDADE_MINIMA_NEWS2 = 16

NivelConsciencia = Literal["Alerta", "Confuso", "Voz", "Dor", "Inconsciente"]

# Aceita as variações mais comuns que o LLM ou o enfermeiro podem enviar (escala ACVPU)
_MAPA_CONSCIENCIA = {
    "a": "Alerta", "alerta": "Alerta", "alert": "Alerta", "lucido": "Alerta", "orientado": "Alerta",
    "c": "Confuso", "confuso": "Confuso", "confusao": "Confuso", "confusao mental": "Confuso",
    "desorientado": "Confuso", "nova confusao": "Confuso",
    "v": "Voz", "voz": "Voz", "verbal": "Voz", "responde a voz": "Voz",
    "p": "Dor", "dor": "Dor", "pain": "Dor", "responde a dor": "Dor",
    "u": "Inconsciente", "inconsciente": "Inconsciente", "unresponsive": "Inconsciente",
    "nao responde": "Inconsciente", "arresponsivo": "Inconsciente",
}

CAMPOS_OBRIGATORIOS = {
    "idade": "idade (anos)",
    "frequencia_respiratoria": "frequência respiratória (irpm)",
    "saturacao_o2": "saturação de O2 (SpO2 %)",
    "oxigenio_suplementar": "se está em ar ambiente ou recebendo oxigênio",
    "pressao_sistolica": "pressão arterial sistólica (mmHg)",
    "frequencia_cardiaca": "frequência cardíaca (bpm)",
    "nivel_consciencia": "nível de consciência (ACVPU)",
    "temperatura": "temperatura (°C)",
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
    idade: Optional[int] = Field(
        default=None, ge=0, le=120,
        description="Idade do paciente em anos completos. Omita se não foi informada."
    )
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
    saturacao_o2: Optional[int] = Field(
        default=None, ge=50, le=100,
        description="Saturação periférica de oxigênio (SpO2) em %. Ex: 95. Omita se não foi informada."
    )
    oxigenio_suplementar: Optional[bool] = Field(
        default=None,
        description="true se o paciente está recebendo oxigênio (cateter, máscara...), false se está em ar ambiente. Omita se não foi informado."
    )
    temperatura: Optional[float] = Field(
        default=None, ge=30.0, le=45.0,
        description="Temperatura corporal em graus Celsius. Ex: 37.5. Omita se não foi informada."
    )
    nivel_consciencia: Optional[NivelConsciencia] = Field(
        default=None,
        description="Estado mental (escala ACVPU): 'Alerta', 'Confuso' (confusão nova), 'Voz' (responde à voz), 'Dor' (responde à dor) ou 'Inconsciente'. Omita se não foi informado."
    )

    @field_validator("nivel_consciencia", mode="before")
    @classmethod
    def normalizar_consciencia(cls, valor):
        if valor is None or not isinstance(valor, str):
            return valor
        return _MAPA_CONSCIENCIA.get(normalizar(valor).strip(" ."), valor)


# --- 2. LÓGICA PURA DO NEWS2 (testável sem LLM) ---

def _pontos_fr(fr: int) -> int:
    if fr <= 8: return 3
    if fr <= 11: return 1
    if fr <= 20: return 0
    if fr <= 24: return 2
    return 3


def _pontos_spo2(spo2: int) -> int:
    # Escala 1 do NEWS2 (a escala 2, para DPOC com retenção de CO2, não está implementada)
    if spo2 <= 91: return 3
    if spo2 <= 93: return 2
    if spo2 <= 95: return 1
    return 0


def _pontos_pas(pas: int) -> int:
    if pas <= 90: return 3
    if pas <= 100: return 2
    if pas <= 110: return 1
    if pas <= 219: return 0
    return 3


def _pontos_fc(fc: int) -> int:
    if fc <= 40: return 3
    if fc <= 50: return 1
    if fc <= 90: return 0
    if fc <= 110: return 1
    if fc <= 130: return 2
    return 3


def _pontos_temp(temp: float) -> int:
    if temp <= 35.0: return 3
    if temp <= 36.0: return 1
    if temp <= 38.0: return 0
    if temp <= 39.0: return 1
    return 2


def calcular_news2(sinais: SinaisVitaisInput) -> dict:
    """
    Calcula o NEWS2 (National Early Warning Score 2, Royal College of Physicians, 2017).

    O campo "status" indica o resultado:
    - "nao_aplicavel": paciente com menos de 16 anos (o NEWS2 não é validado em crianças).
    - "incompleto": falta algum dado; nada é estimado.
    - "calculado": escore e classificação disponíveis.

    Regras de classificação:
    - VERMELHO: escore total >= 7 (resposta de emergência) ou paciente inconsciente.
    - AMARELO: escore total 5-6, ou qualquer parâmetro isolado com 3 pontos.
    - VERDE: demais casos.
    """
    dados = sinais.model_dump()
    informados = {k: v for k, v in dados.items() if v is not None}

    if sinais.idade is not None and sinais.idade < IDADE_MINIMA_NEWS2:
        return {
            "status": "nao_aplicavel",
            "motivo": f"Paciente pediátrico ({sinais.idade} anos): o NEWS2 só é validado a partir de {IDADE_MINIMA_NEWS2} anos.",
            "sinais_vitais": informados,
        }

    faltando = [rotulo for campo, rotulo in CAMPOS_OBRIGATORIOS.items() if dados[campo] is None]
    if faltando:
        return {"status": "incompleto", "faltando": faltando, "sinais_vitais": informados}

    detalhe = {
        "frequencia_respiratoria": _pontos_fr(sinais.frequencia_respiratoria),
        "saturacao_o2": _pontos_spo2(sinais.saturacao_o2),
        "oxigenio_suplementar": 2 if sinais.oxigenio_suplementar else 0,
        "pressao_sistolica": _pontos_pas(sinais.pressao_sistolica),
        "frequencia_cardiaca": _pontos_fc(sinais.frequencia_cardiaca),
        "nivel_consciencia": 0 if sinais.nivel_consciencia == "Alerta" else 3,
        "temperatura": _pontos_temp(sinais.temperatura),
    }
    score = sum(detalhe.values())

    # Regra extra do projeto (além do NEWS2): inconsciente nunca fica abaixo de VERMELHO
    if score >= 7 or sinais.nivel_consciencia == "Inconsciente":
        classificacao = "VERMELHO"
    elif score >= 5 or max(detalhe.values()) == 3:
        classificacao = "AMARELO"
    else:
        classificacao = "VERDE"

    return {
        "status": "calculado",
        "escore": score,
        "classificacao": classificacao,
        "pontos_por_parametro": detalhe,
        "sinais_vitais": dados,
    }


_TEXTO_CLASSIFICACAO = {
    "VERMELHO": "VERMELHO (Emergência). Risco alto. Requer Sala de Emergência/UTI imediata.",
    "AMARELO": "AMARELO (Urgência). Risco moderado. Avaliação médica rápida necessária.",
    "VERDE": "VERDE (Pouco urgente). Risco baixo. Fluxo padrão de atendimento.",
}


# --- 3. FERRAMENTA EXPOSTA AO AGENTE ---

@tool("calcular_escore_gravidade", args_schema=SinaisVitaisInput, response_format="content_and_artifact")
def calcular_escore_gravidade(
    idade: Optional[int] = None,
    frequencia_cardiaca: Optional[int] = None,
    pressao_sistolica: Optional[int] = None,
    frequencia_respiratoria: Optional[int] = None,
    saturacao_o2: Optional[int] = None,
    oxigenio_suplementar: Optional[bool] = None,
    temperatura: Optional[float] = None,
    nivel_consciencia: Optional[str] = None,
) -> tuple[str, dict]:
    """
    Calcula o escore de gravidade clínica do paciente adulto pelo protocolo NEWS2.
    Envie SOMENTE os dados informados explicitamente pelo enfermeiro; omita os demais.
    Se faltar algum dado, a ferramenta responde quais ainda precisam ser coletados.
    Para menores de 16 anos, a ferramenta informa que o escore adulto não se aplica.
    """
    sinais = SinaisVitaisInput(
        idade=idade,
        frequencia_cardiaca=frequencia_cardiaca,
        pressao_sistolica=pressao_sistolica,
        frequencia_respiratoria=frequencia_respiratoria,
        saturacao_o2=saturacao_o2,
        oxigenio_suplementar=oxigenio_suplementar,
        temperatura=temperatura,
        nivel_consciencia=nivel_consciencia,
    )
    resultado = calcular_news2(sinais)

    if resultado["status"] == "nao_aplicavel":
        texto = (
            f"ESCORE NÃO APLICÁVEL: {resultado['motivo']} Não classifique pelo NEWS2. "
            "Consulte o protocolo pediátrico (`buscar_protocolo_interno`) e o pediatra de plantão."
        )
        return texto, resultado

    if resultado["status"] == "incompleto":
        texto = (
            "DADOS INSUFICIENTES: o escore NÃO foi calculado. Pergunte ao enfermeiro: "
            + "; ".join(resultado["faltando"]) + ". Não estime valores."
        )
        return texto, resultado

    prefixo = "ALERTA: " if resultado["classificacao"] == "VERMELHO" else ""
    texto = f"{prefixo}Score NEWS2={resultado['escore']}. Classificação: {_TEXTO_CLASSIFICACAO[resultado['classificacao']]}"
    return texto, resultado
