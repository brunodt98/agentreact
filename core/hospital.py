"""
Dados do hospital (SIMULADOS): leitos por ala e escala do plantão.

Fonte única para as ferramentas do agente e para o painel do plantão, para que
os dois mostrem sempre os mesmos números. Num hospital real, este módulo leria
o sistema de gestão de leitos e a escala de RH.
"""

TURNO = "07h às 19h"

# Ala -> capacidade e ocupação atual
LEITOS = {
    "Emergência": {"total": 8, "ocupados": 8},
    "UTI": {"total": 10, "ocupados": 8},
    "Enfermaria Adulto": {"total": 40, "ocupados": 25},
    "Enfermaria Pediátrica": {"total": 12, "ocupados": 8},
}

# Especialidade -> médico de plantão
ESCALA_PLANTAO = {
    "Cardiologia": {"nome": "Dr. Carlos Mendes", "ramal": "404", "status": "Disponível"},
    "Neurologia": {"nome": "Dra. Ana Silva", "ramal": "412", "status": "Em cirurgia"},
    "Clínica Geral": {"nome": "Dr. Roberto Gomes", "ramal": "100", "status": "Disponível"},
    "Pediatria": {"nome": "Dra. Julia Costa", "ramal": "205", "status": "Disponível"},
    "Ortopedia": {"nome": "Dr. Fernando Souza", "ramal": "330", "status": "Em atendimento"},
    "Cirurgia Geral": {"nome": "Dra. Marina Lopes", "ramal": "318", "status": "Disponível"},
}


def vagas(ala: str) -> int:
    leitos = LEITOS[ala]
    return leitos["total"] - leitos["ocupados"]
