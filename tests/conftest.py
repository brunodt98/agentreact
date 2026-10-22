"""Configuração comum dos testes."""
import os

# Os testes não usam rede: desliga o envio de rastros ao LangSmith mesmo que o .env o ative.
# (load_dotenv não sobrescreve variáveis que já existem no ambiente.)
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
