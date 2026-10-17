from langchain_core.tools import tool
from pydantic import BaseModel, Field

# --- 1. SCHEMAS DE VALIDAÇÃO (PYDANTIC) ---

class SinaisVitaisInput(BaseModel):
    """Esquema de entrada obrigatório para a calculadora de risco."""
    frequencia_cardiaca: int = Field(
        description="Frequência cardíaca do paciente em bpm (batimentos por minuto). Deve ser um número inteiro inteiro."
    )
    pressao_sistolica: int = Field(
        description="Apenas o valor sistólico da pressão arterial em mmHg (o valor mais alto). Ex: se for 120/80, informe 120."
    )
    frequencia_respiratoria: int = Field(
        description="Frequência respiratória em irpm (incursões respiratórias por minuto). Deve ser um número inteiro."
    )
    temperatura: float = Field(
        description="Temperatura corporal em graus Celsius. Use ponto flutuante. Ex: 37.5"
    )
    nivel_consciencia: str = Field(
        description="Estado mental do paciente. Valores aceitos: 'Alerta', 'Voz' (responde a voz), 'Dor' (responde a dor) ou 'Inconsciente'."
    )

# --- 2. FERRAMENTAS CLÍNICAS ---

@tool("calcular_escore_gravidade", args_schema=SinaisVitaisInput)
def calcular_escore_gravidade(
    frequencia_cardiaca: int, 
    pressao_sistolica: int, 
    frequencia_respiratoria: int, 
    temperatura: float, 
    nivel_consciencia: str
) -> str:
    """
    Calcula o escore de gravidade clínica do paciente (baseado numa versão simplificada do protocolo MEWS).
    Utilize esta ferramenta APENAS quando tiver coletado todos os sinais vitais mínimos do paciente.
    """
    score = 0
    
    # Lógica simplificada de pontuação de risco (MEWS - Modified Early Warning Score)
    
    # Frequência Cardíaca
    if frequencia_cardiaca <= 40 or frequencia_cardiaca >= 130: score += 3
    elif 111 <= frequencia_cardiaca <= 129: score += 2
    elif 41 <= frequencia_cardiaca <= 50 or 101 <= frequencia_cardiaca <= 110: score += 1
    
    # Pressão Sistólica
    if pressao_sistolica <= 70: score += 3
    elif 71 <= pressao_sistolica <= 80: score += 2
    elif 81 <= pressao_sistolica <= 100: score += 1
    elif pressao_sistolica >= 200: score += 2
    
    # Frequência Respiratória
    if frequencia_respiratoria < 9 or frequencia_respiratoria >= 30: score += 3
    elif 21 <= frequencia_respiratoria <= 29: score += 2
    
    # Temperatura
    if temperatura < 35.0 or temperatura >= 38.5: score += 2
    
    # Nível de Consciência
    if nivel_consciencia.lower() == 'inconsciente': score += 3
    elif nivel_consciencia.lower() in ['dor', 'voz']: score += 2
    
    # --- RESULTADO E CLASSIFICAÇÃO ---
    if score >= 5 or nivel_consciencia.lower() == 'inconsciente':
        return f"ALERTA: Score MEWS={score}. Classificação: VERMELHO (Emergência). Risco altíssimo. Requer UTI ou Sala de Emergência imediata."
    elif score >= 3:
        return f"Score MEWS={score}. Classificação: AMARELO (Urgência). Risco moderado a alto. Avaliação médica rápida necessária."
    else:
        return f"Score MEWS={score}. Classificação: VERDE (Pouco urgente). Risco baixo. Fluxo padrão de atendimento."