# 🏥 Agente Clínico de Triagem Hospitalar

![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-ReAct%20Agent-orange)

Um assistente inteligente (AI Agent) baseado na arquitetura **ReAct** (Reasoning and Acting) desenvolvido para auxiliar enfermeiros na triagem de pacientes em ambiente hospitalar. O foco principal do projeto é a **segurança clínica** e a **prevenção de alucinações**, garantindo que as decisões de risco sigam protocolos rigorosos.

## 🧠 Arquitetura e Tecnologias

Este projeto foi construído utilizando um ecossistema moderno de IA Generativa e orquestração de fluxos:

*   **[Streamlit](https://streamlit.io/):** Interface de usuário (UI) simples e interativa, simulando o chat de triagem.
*   **[LangGraph](https://python.langchain.com/v0.1/docs/langgraph/):** Gerenciamento de estado (StateGraph) e fluxo do agente, permitindo memória contínua e a funcionalidade de *Human-in-the-loop*.
*   **[LangChain](https://www.langchain.com/):** Framework base para integração das ferramentas e chamadas ao LLM.
*   **Google Gemini (1.5 / 2.5 Flash):** Modelo fundacional (LLM) configurado com `temperature=0.0` para respostas determinísticas.
*   **[Pydantic](https://docs.pydantic.dev/):** Camada de validação de dados estrita para garantir que as ferramentas clínicas recebam exatamente os tipos de dados esperados (ex: números inteiros para batimentos cardíacos).

## 🛠️ Ferramentas do Agente (Tools)

O agente tem autonomia para chamar as seguintes ferramentas em Python de acordo com o relato do paciente:

1.  `calcular_escore_gravidade`: Recebe sinais vitais validados e calcula o risco clínico baseado no protocolo MEWS (Modified Early Warning Score), retornando classificação de cores (Vermelho, Amarelo, Verde).
2.  `consultar_leitos`: Simula uma consulta ao banco de dados do hospital para verificar vagas em alas específicas (ex: UTI, Enfermaria).
3.  `buscar_medico_plantao`: Consulta a escala de RH para retornar o médico especialista disponível e seu ramal.
4.  `buscar_protocolo_interno`: Sistema simulado de RAG (Retrieval-Augmented Generation) para buscar diretrizes hospitalares específicas (ex: Protocolo de AVC ou Sepse).

## 🚀 Como instalar e rodar localmente

Siga os passos abaixo para executar a aplicação na sua máquina:

### 1. Clone o repositório
```bash
git clone https://github.com/emersonaparecidosilva/agentreact.git
cd agentreact
```

### 2. Crie e ative o ambiente virtual
```bash
python -m venv .venv
# No Windows:
.venv\Scripts\activate
# No Linux/Mac:
source .venv/bin/activate
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente
Crie um arquivo `.env` na raiz do projeto e insira suas chaves de API:
```env
GOOGLE_API_KEY="sua-chave-do-google-gemini-aqui"
LANGCHAIN_TRACING_V2="true"
LANGCHAIN_API_KEY="sua-chave-do-langsmith-aqui"
LANGCHAIN_PROJECT="agente_triagem_v1"
```
*(Nota: O arquivo `.env` está no `.gitignore` para proteger suas credenciais).*

### 5. Inicie a aplicação
```bash
streamlit run app.py
```

## 🔒 Regras de Segurança (System Prompt)
O agente foi instruído estritamente para:
- **Nunca** inventar diagnósticos médicos.
- Solicitar informações ausentes de sinais vitais antes de acionar a calculadora de risco.
- Basear o encaminhamento **apenas** no retorno matemático das funções Python, isolando o raciocínio clínico da inferência do LLM.

---
*Desenvolvido como projeto de estudo prático sobre Agentes Autônomos em Saúde.*