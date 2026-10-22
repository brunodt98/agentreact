"""
Detecção determinística de Sintomas de Risco Imediato (red flags).

Roda em Python ANTES do LLM: a segurança do paciente não pode depender do modelo
"lembrar" de uma regra do prompt. Na dúvida, o detector prefere o falso positivo
(o enfermeiro confirma ou descarta), nunca o falso negativo.
"""
import re

from utils.text import normalizar

# Categoria -> expressões regulares sobre o texto normalizado (minúsculo e sem acento)
RED_FLAGS: dict[str, list[str]] = {
    "Dor torácica": [
        r"dor (no|em|ao) peito", r"dor (toracica|precordial)", r"aperto no peito", r"infarto",
    ],
    "Dificuldade respiratória grave": [
        r"falta de ar (intensa|grave|severa|importante)", r"dispneia (intensa|grave|severa|importante)",
        r"(nao|mal) consegue respirar", r"sufocando", r"cianose", r"cianotic[oa]", r"labios roxos",
    ],
    "Alteração/perda de consciência": [
        r"desmai(o|ou)", r"perd(a|eu) (de |a )?consciencia", r"inconsciente", r"desacordad[oa]",
        r"nao responde", r"convuls(ao|ionando|ionou)", r"sincope",
    ],
    "Sangramento ativo massivo": [
        r"sangramento (ativo|intenso|massivo|abundante|importante)", r"hemorragia",
        r"sangrando muito", r"vomit(o|ando) (com )?sangue", r"hematemese",
    ],
    "Suspeita de AVC": [
        r"\bavc\b", r"derrame", r"boca torta", r"desvio de rima", r"fala enrolada",
        r"perda (subita )?de forca", r"hemiparesia", r"hemiplegia",
    ],
}

# Palavras que negam o sintoma quando aparecem logo antes dele, na mesma oração.
_NEGACOES = {"nega", "negou", "sem", "nao", "ausencia", "ausente", "descarta", "descartado"}
# Delimitadores de oração: a negação de uma não "vaza" para a próxima.
_SEPARADORES = re.compile(r"[,;.\n]|\b(?:mas|porem|com|e|apresenta|refere|relata)\b")
_JANELA_NEGACAO = 4  # nº de palavras olhadas antes do sintoma

_PADROES = {categoria: [re.compile(p) for p in padroes] for categoria, padroes in RED_FLAGS.items()}


def _negado(texto: str, inicio: int) -> bool:
    antes = texto[:inicio]
    # Considera apenas o trecho da oração atual
    oracao = _SEPARADORES.split(antes)[-1] if antes else ""
    palavras = re.findall(r"\w+", oracao)[-_JANELA_NEGACAO:]
    return any(p in _NEGACOES for p in palavras)


def detectar_red_flags(texto: str) -> list[str]:
    """Retorna as categorias de risco imediato encontradas no texto (sem duplicatas, em ordem fixa)."""
    texto_norm = normalizar(texto)
    encontradas = []
    for categoria, padroes in _PADROES.items():
        for padrao in padroes:
            if any(not _negado(texto_norm, m.start()) for m in padrao.finditer(texto_norm)):
                encontradas.append(categoria)
                break
    return encontradas
