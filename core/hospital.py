"""
Dados do hospital (SIMULADOS): leitos de cada ala, pacientes internados e equipe do plantão.

Fonte única para as ferramentas do agente e para o painel do plantão, para que
os dois mostrem sempre os mesmos números. Num hospital real, este módulo leria
o sistema de gestão de leitos e a escala de RH.
"""
import random

TURNO = "07h às 19h"

# --- 1. ALAS ---
# Ala -> sigla dos leitos, capacidade e ocupação atual
_ALAS = {
    "Emergência": {"sigla": "EM", "total": 8, "ocupados": 8},
    "UTI": {"sigla": "UTI", "total": 10, "ocupados": 8},
    "Enfermaria Adulto": {"sigla": "AD", "total": 40, "ocupados": 25},
    "Enfermaria Pediátrica": {"sigla": "PED", "total": 12, "ocupados": 8},
}

# --- 2. EQUIPE ---
# Especialidade -> médico de plantão. "local" é onde ele está agora; "leito", quem está atendendo.
ESCALA_PLANTAO = {
    "Cardiologia": {"nome": "Dr. Carlos Mendes", "ramal": "404", "status": "Disponível", "local": "UTI"},
    "Neurologia": {"nome": "Dra. Ana Silva", "ramal": "412", "status": "Em cirurgia", "local": "Centro Cirúrgico"},
    "Clínica Geral": {"nome": "Dr. Roberto Gomes", "ramal": "100", "status": "Disponível", "local": "Emergência"},
    "Pediatria": {"nome": "Dra. Julia Costa", "ramal": "205", "status": "Disponível", "local": "Enfermaria Pediátrica"},
    "Ortopedia": {"nome": "Dr. Fernando Souza", "ramal": "330", "status": "Em atendimento", "local": "Emergência",
                  "leito": "EM-03"},
    "Cirurgia Geral": {"nome": "Dra. Marina Lopes", "ramal": "318", "status": "Disponível", "local": "Enfermaria Adulto"},
}

# Ala -> enfermeiros responsáveis no turno
ENFERMAGEM = {
    "Emergência": ["Enf. Paula Ramos", "Enf. Diego Alves"],
    "UTI": ["Enf. Beatriz Nunes", "Enf. Tiago Rocha"],
    "Enfermaria Adulto": ["Enf. Camila Duarte", "Enf. Lucas Prado", "Enf. Renata Lima"],
    "Enfermaria Pediátrica": ["Enf. Sofia Martins"],
}

# --- 3. LEITOS E PACIENTES INTERNADOS ---
# Gerados com semente fixa: o painel mostra sempre o mesmo hospital.
_NOMES = ["Maria S.", "João P.", "Ana L.", "Carlos M.", "Francisca R.", "Antônio F.", "Luiza C.", "Pedro H.",
          "Helena B.", "José A.", "Rita O.", "Paulo V.", "Sandra T.", "Marcos D.", "Teresa G.", "Raimundo N.",
          "Cláudia E.", "Sérgio L.", "Vera M.", "Jorge K.", "Lúcia P.", "Fábio R.", "Rosa A.", "Eduardo S.",
          "Márcia F.", "Gilberto C.", "Denise H.", "Roberto J.", "Sônia Q.", "Alberto Z."]
_NOMES_CRIANCAS = ["Miguel", "Alice", "Arthur", "Laura", "Heitor", "Valentina", "Davi", "Sophia"]

_MOTIVOS = {
    "Emergência": ["Dor torácica em observação", "Crise asmática", "Fratura de fêmur", "Cólica renal",
                   "Desidratação", "Crise hipertensiva", "Trauma craniano leve", "Hipoglicemia"],
    "UTI": ["Pós-operatório cardíaco", "Sepse", "Insuficiência respiratória", "AVC isquêmico",
            "Choque séptico", "Pós-PCR", "Pneumonia grave", "Cetoacidose diabética"],
    "Enfermaria Adulto": ["Pneumonia", "Erisipela", "Pós-operatório", "ICC descompensada", "Pielonefrite",
                          "Celulite", "DPOC exacerbado", "Pancreatite leve", "Diabetes descompensado"],
    "Enfermaria Pediátrica": ["Bronquiolite", "Gastroenterite", "Pneumonia", "Pós-operatório",
                              "Crise asmática", "Infecção urinária"],
}

# Proporção de pacientes críticos / em atenção em cada ala (o resto é estável)
_GRAVIDADE = {
    "Emergência": (0.25, 0.5),
    "UTI": (0.6, 0.3),
    "Enfermaria Adulto": (0.04, 0.2),
    "Enfermaria Pediátrica": (0.0, 0.25),
}


def _gerar_leitos() -> dict[str, list[dict]]:
    sorteio = random.Random(2026)
    leitos = {}
    for ala, info in _ALAS.items():
        # Leitos ocupados espalhados pela ala (como num hospital de verdade, não todos no começo)
        ocupados = set(sorteio.sample(range(info["total"]), info["ocupados"]))
        critico, atencao = _GRAVIDADE[ala]
        lista = []
        for i in range(info["total"]):
            leito = {"codigo": f"{info['sigla']}-{i + 1:02d}", "paciente": None}
            if i in ocupados:
                pediatrico = ala == "Enfermaria Pediátrica"
                r = sorteio.random()
                leito["paciente"] = {
                    "nome": sorteio.choice(_NOMES_CRIANCAS if pediatrico else _NOMES),
                    "idade": sorteio.randint(1, 14) if pediatrico else sorteio.randint(19, 88),
                    "motivo": sorteio.choice(_MOTIVOS[ala]),
                    "gravidade": "critico" if r < critico else ("atencao" if r < critico + atencao else "estavel"),
                    "dias": sorteio.randint(0, 9) if ala != "Emergência" else 0,
                }
            lista.append(leito)
        leitos[ala] = lista
    return leitos


LEITOS_DETALHE = _gerar_leitos()
# O ortopedista está atendendo o EM-03: o caso do leito precisa combinar com a especialidade
LEITOS_DETALHE["Emergência"][2]["paciente"].update(motivo="Fratura de fêmur", gravidade="atencao")

# Ala -> capacidade e ocupação atual (resumo usado pelas ferramentas do agente)
LEITOS = {
    ala: {"total": len(lista), "ocupados": sum(1 for l in lista if l["paciente"])}
    for ala, lista in LEITOS_DETALHE.items()
}


def vagas(ala: str) -> int:
    leitos = LEITOS[ala]
    return leitos["total"] - leitos["ocupados"]


def medicos_em(local: str) -> list[tuple[str, dict]]:
    """Médicos que estão agora no local, como (especialidade, dados)."""
    return [(esp, m) for esp, m in ESCALA_PLANTAO.items() if m.get("local") == local]


def medico_no_leito(codigo: str):
    """Médico que está atendendo o paciente deste leito, ou None."""
    return next((m for m in ESCALA_PLANTAO.values() if m.get("leito") == codigo), None)
