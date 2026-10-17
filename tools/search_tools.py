from langchain_core.tools import tool
from pydantic import BaseModel, Field

class BuscaProtocoloInput(BaseModel):
    sintoma_ou_condicao: str = Field(
        description="O sintoma ou suspeita clínica para buscar no manual de diretrizes. Ex: 'dor no peito', 'sepse', 'avc'."
    )

@tool("buscar_protocolo_interno", args_schema=BuscaProtocoloInput)
def buscar_protocolo_interno(sintoma_ou_condicao: str) -> str:
    """
    Busca as diretrizes e protocolos internos do hospital para uma condição específica.
    Use esta ferramenta para saber a conduta padrão do hospital antes de classificar o risco final.
    """
    condicao = sintoma_ou_condicao.lower()
    
    # Base de conhecimento simulada (Mock)
    if "dor no peito" in condicao or "infarto" in condicao:
        return "Protocolo Dor Torácica: Prioridade máxima (Vermelho). Solicitar ECG em até 10 minutos. Acionar Cardiologista imediatamente."
    elif "sepse" in condicao or "febre" in condicao:
        return "Protocolo Sepse: Avaliar qSOFA. Se suspeita de infecção com pressão baixa ou alteração mental, acionar emergência e preparar coleta de lactato."
    elif "avc" in condicao or "derrame" in condicao:
        return "Protocolo AVC: Acionar código AVC. Tomografia sem contraste imediata. Risco Vermelho."
    else:
        return f"Nenhum protocolo restrito encontrado para '{sintoma_ou_condicao}'. Seguir fluxo padrão de triagem (MEWS)."