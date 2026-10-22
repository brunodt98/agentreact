from datetime import datetime

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from core.hospital import ESCALA_PLANTAO, LEITOS, vagas
from utils.logger import logger
from utils.text import normalizar

# --- 1. SCHEMAS DE VALIDAÇÃO (PYDANTIC) ---

class ConsultaLeitosInput(BaseModel):
    ala: str = Field(
        description="A ala do hospital onde deseja verificar vagas. Valores permitidos: 'UTI', 'Enfermaria Adulto', 'Enfermaria Pediátrica', 'Emergência'."
    )

class BuscaMedicoInput(BaseModel):
    especialidade: str = Field(
        description="A especialidade médica necessária. Ex: 'Cardiologia', 'Neurologia', 'Clínica Geral', 'Pediatria', 'Ortopedia', 'Cirurgia Geral'."
    )

class AcionarEmergenciaInput(BaseModel):
    motivo: str = Field(
        description="Resumo objetivo do motivo do acionamento, citando sinais de alarme e/ou escore. Ex: 'Dor no peito irradiando, NEWS2 7'."
    )
    especialidade: str = Field(
        default="Clínica Geral",
        description="Especialidade a ser acionada junto com a equipe de emergência. Ex: 'Cardiologia', 'Neurologia'."
    )

# --- 2. DADOS DO HOSPITAL (simulados, em core/hospital.py) ---


def _buscar_chave(valor: str, opcoes) -> str | None:
    """Encontra a chave correspondente ignorando maiúsculas e acentos ('enfermaria pediatrica' -> 'Enfermaria Pediátrica')."""
    alvo = normalizar(valor).strip()
    return next((chave for chave in opcoes if normalizar(chave) == alvo), None)

# --- 3. FERRAMENTAS DE CONSULTA (somente leitura) ---

@tool("consultar_leitos", args_schema=ConsultaLeitosInput)
def consultar_leitos(ala: str) -> str:
    """
    Consulta o sistema de gestão hospitalar para verificar a disponibilidade de leitos em uma ala específica.
    """
    ala_encontrada = _buscar_chave(ala, LEITOS)
    if ala_encontrada is None:
        return f"Erro: A ala '{ala}' não foi encontrada no sistema. Alas válidas: {', '.join(LEITOS)}."

    qtd = vagas(ala_encontrada)
    if qtd > 0:
        return f"Existem {qtd} vaga(s) disponível(is) na ala {ala_encontrada}."
    return f"ALERTA SISTEMA: Não há vagas na ala {ala_encontrada} no momento. Acionar protocolo de superlotação."

@tool("buscar_medico_plantao", args_schema=BuscaMedicoInput)
def buscar_medico_plantao(especialidade: str) -> str:
    """
    Consulta o sistema de RH/Escalas para identificar qual médico especialista está de plantão no momento e seu ramal.
    """
    especialidade_encontrada = _buscar_chave(especialidade, ESCALA_PLANTAO)
    if especialidade_encontrada is None:
        return f"Erro: Nenhuma escala encontrada para a especialidade '{especialidade}'. Especialidades válidas: {', '.join(ESCALA_PLANTAO)}."

    medico = ESCALA_PLANTAO[especialidade_encontrada]
    return (f"Plantão {especialidade_encontrada}: {medico['nome']} "
            f"(Ramal {medico['ramal']}) - Status atual: {medico['status']}.")

# --- 4. FERRAMENTAS DE AÇÃO (exigem aprovação do enfermeiro) ---

@tool("acionar_equipe_emergencia", args_schema=AcionarEmergenciaInput)
def acionar_equipe_emergencia(motivo: str, especialidade: str = "Clínica Geral") -> str:
    """
    Aciona a equipe de emergência (código vermelho) e o especialista de plantão.
    Use quando houver sinal de alarme ou classificação VERMELHO.
    Esta ação só é executada após aprovação explícita do enfermeiro.
    """
    horario = datetime.now().strftime("%H:%M:%S")
    especialidade_encontrada = _buscar_chave(especialidade, ESCALA_PLANTAO) or "Clínica Geral"
    medico = ESCALA_PLANTAO[especialidade_encontrada]
    logger.warning("CÓDIGO VERMELHO acionado | motivo=%s | especialidade=%s", motivo, especialidade_encontrada)
    return (f"Equipe de emergência acionada às {horario}. Motivo: {motivo}. "
            f"Especialista notificado: {medico['nome']} ({especialidade_encontrada}, ramal {medico['ramal']}, "
            f"status: {medico['status']}).")

# Ferramentas que alteram o mundo real e por isso passam pelo human-in-the-loop
FERRAMENTAS_SENSIVEIS = {"acionar_equipe_emergencia"}
