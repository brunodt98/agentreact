"""
Módulo central de ferramentas.
Importa as ferramentas clínicas, de sistema e de pesquisa para as expor como uma lista única para o LangGraph.
"""

from .clinical_tools import calcular_escore_gravidade
from .system_tools import consultar_leitos, buscar_medico_plantao
from .search_tools import buscar_protocolo_interno

# Agrupamos todas as ferramentas numa lista constante.
ALL_TOOLS = [
    calcular_escore_gravidade,
    consultar_leitos,
    buscar_medico_plantao,
    buscar_protocolo_interno
]

# O __all__ define exatamente o que será exportado
__all__ = [
    "ALL_TOOLS",
    "calcular_escore_gravidade",
    "consultar_leitos",
    "buscar_medico_plantao",
    "buscar_protocolo_interno"
]