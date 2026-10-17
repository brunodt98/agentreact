from langchain_core.tools import tool
from pydantic import BaseModel, Field

# --- 1. SCHEMAS DE VALIDAÇÃO (PYDANTIC) ---

class ConsultaLeitosInput(BaseModel):
    ala: str = Field(
        description="A ala do hospital onde deseja verificar vagas. Valores permitidos: 'UTI', 'Enfermaria Adulto', 'Enfermaria Pediátrica', 'Emergência'."
    )

class BuscaMedicoInput(BaseModel):
    especialidade: str = Field(
        description="A especialidade médica necessária. Ex: 'Cardiologia', 'Neurologia', 'Clínica Geral', 'Pediatria', 'Ortopedia'."
    )

# --- 2. FERRAMENTAS DE SISTEMA (MOCKS) ---

@tool("consultar_leitos", args_schema=ConsultaLeitosInput)
def consultar_leitos(ala: str) -> str:
    """
    Consulta o sistema de gestão hospitalar para verificar a disponibilidade de leitos em uma ala específica.
    """
    vagas_hospital = {
        "UTI": 2,
        "Enfermaria Adulto": 15,
        "Enfermaria Pediátrica": 4,
        "Emergência": 0
    }
    
    # Tratamento especial para siglas, garantindo que 'UTI' não vire 'Uti'
    if ala.upper() == "UTI":
        ala_formatada = "UTI"
    else:
        ala_formatada = ala.title()
    
    if ala_formatada in vagas_hospital:
        qtd = vagas_hospital[ala_formatada]
        if qtd > 0:
            return f"Existem {qtd} vaga(s) disponível(is) na ala {ala_formatada}."
        else:
            return f"ALERTA SISTEMA: Não há vagas na ala {ala_formatada} no momento. Acionar protocolo de superlotação."
    else:
        return f"Erro: A ala '{ala}' não foi encontrada no sistema. Verifique o nome e tente novamente."

@tool("buscar_medico_plantao", args_schema=BuscaMedicoInput)
def buscar_medico_plantao(especialidade: str) -> str:
    """
    Consulta o sistema de RH/Escalas para identificar qual médico especialista está de plantão no momento e seu ramal.
    """
    escala_plantao = {
        "Cardiologia": {"nome": "Dr. Carlos Mendes", "ramal": "404", "status": "Disponível"},
        "Neurologia": {"nome": "Dra. Ana Silva", "ramal": "412", "status": "Em cirurgia"},
        "Clínica Geral": {"nome": "Dr. Roberto Gomes", "ramal": "100", "status": "Disponível"},
        "Pediatria": {"nome": "Dra. Julia Costa", "ramal": "205", "status": "Disponível"},
        "Ortopedia": {"nome": "Dr. Fernando Souza", "ramal": "330", "status": "Disponível"}
    }
    
    especialidade_formatada = especialidade.title()
    
    if especialidade_formatada in escala_plantao:
        medico = escala_plantao[especialidade_formatada]
        return (f"Plantão {especialidade_formatada}: {medico['nome']} "
                f"(Ramal {medico['ramal']}) - Status atual: {medico['status']}.")
    else:
        return f"Erro: Nenhuma escala encontrada para a especialidade '{especialidade}'."