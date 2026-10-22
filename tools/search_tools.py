from langchain_core.tools import tool
from pydantic import BaseModel, Field

from utils.text import normalizar

class BuscaProtocoloInput(BaseModel):
    sintoma_ou_condicao: str = Field(
        description="O sintoma ou suspeita clínica para buscar no manual de diretrizes. Ex: 'dor no peito', 'sepse', 'avc'."
    )

# Base de conhecimento simulada (Mock): palavras-chave (sem acento) -> protocolo
PROTOCOLOS = [
    (
        ("dor no peito", "dor toracica", "precordial", "infarto"),
        "Protocolo Dor Torácica: Prioridade máxima (Vermelho). Solicitar ECG em até 10 minutos. Acionar Cardiologista imediatamente.",
    ),
    (
        ("sepse", "septic", "infeccao", "febre"),
        "Protocolo Sepse: Avaliar qSOFA. Se suspeita de infecção com pressão baixa ou alteração mental, acionar emergência e preparar coleta de lactato.",
    ),
    (
        ("avc", "derrame", "boca torta", "perda de forca", "fala enrolada", "hemiparesia"),
        "Protocolo AVC: Acionar código AVC. Tomografia sem contraste imediata. Risco Vermelho.",
    ),
]

@tool("buscar_protocolo_interno", args_schema=BuscaProtocoloInput)
def buscar_protocolo_interno(sintoma_ou_condicao: str) -> str:
    """
    Busca as diretrizes e protocolos internos do hospital para uma condição específica.
    Use esta ferramenta para saber a conduta padrão do hospital antes de classificar o risco final.
    """
    condicao = normalizar(sintoma_ou_condicao)

    encontrados = [texto for chaves, texto in PROTOCOLOS if any(chave in condicao for chave in chaves)]
    if encontrados:
        return "\n".join(encontrados)
    return f"Nenhum protocolo restrito encontrado para '{sintoma_ou_condicao}'. Seguir fluxo padrão de triagem (MEWS)."
