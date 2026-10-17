import logging
import sys

def setup_logger(name="AgenteTriagem"):
    """
    Configura um logger padronizado para o projeto.
    Isso ajuda a debugar problemas e manter um registro (auditoria) do que o agente está fazendo.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Evita adicionar múltiplos handlers se a função for chamada várias vezes
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

# Instância global para ser importada em outros arquivos
logger = setup_logger()