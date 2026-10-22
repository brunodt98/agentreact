import unicodedata


def normalizar(texto: str) -> str:
    """Converte para minúsculas e remove acentos ('Dor Torácica' -> 'dor toracica')."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower()


def conteudo_para_texto(conteudo) -> str:
    """
    Extrai apenas o texto de uma mensagem. O Gemini às vezes devolve o conteúdo
    como lista de blocos ([{"type": "text", "text": ...}, ...]) em vez de string.
    """
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        partes = []
        for bloco in conteudo:
            if isinstance(bloco, str):
                partes.append(bloco)
            elif isinstance(bloco, dict) and "text" in bloco:
                partes.append(bloco["text"])
        return "\n".join(partes)
    return str(conteudo)
