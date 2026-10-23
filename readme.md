# 🏥 Agente Clínico de Triagem Hospitalar

![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-ReAct%20Agent-orange)

Um assistente inteligente (AI Agent) baseado na arquitetura **ReAct** (Reasoning and Acting) desenvolvido para auxiliar enfermeiros na triagem de pacientes em ambiente hospitalar. O foco principal do projeto é a **segurança clínica** e a **prevenção de alucinações**, garantindo que as decisões de risco sigam protocolos rigorosos.

## 🧠 Arquitetura e Tecnologias

Este projeto foi construído utilizando um ecossistema moderno de IA Generativa e orquestração de fluxos:

*   **[Streamlit](https://streamlit.io/):** Interface clínica em duas colunas: chat de triagem à esquerda e painel do paciente à direita (cartão de risco com escore NEWS2 e lista de sinais vitais com a pontuação de cada um). A autorização de ações sensíveis aparece dentro da conversa, logo abaixo da pergunta da assistente, e a legenda fica no botão **Ajuda**. O chat tem visual de aplicativo de mensagens, com a assistente **Clara** (avatar em `assets/`, editável no SVG). Tema em `.streamlit/config.toml` e componentes em `ui/componentes.py`.
*   **[LangGraph](https://python.langchain.com/v0.1/docs/langgraph/):** Gerenciamento de estado (StateGraph) e fluxo do agente, permitindo memória contínua e a funcionalidade de *Human-in-the-loop*.
*   **[LangChain](https://www.langchain.com/):** Framework base para integração das ferramentas e chamadas ao LLM.
*   **Google Gemini (2.5 Flash, configurável via `TRIAGEM_MODELO`):** Modelo fundacional (LLM) configurado com `temperature=0.0` para respostas determinísticas.
*   **[pytest](https://docs.pytest.org/):** Testes das regras clínicas e do fluxo do grafo (com LLM simulado).
*   **[Pydantic](https://docs.pydantic.dev/):** Camada de validação de dados estrita para garantir que as ferramentas clínicas recebam exatamente os tipos de dados esperados (ex: números inteiros para batimentos cardíacos).

## 🔀 Fluxo do grafo

```
START → red_flags → agent ──(resposta)──────────────→ END
                      │  ↑
                      │  └── registrar_resultados ← tools
                      │                               ↑
                      └──(ação sensível)→ aprovacao_humana (pausa: enfermeiro aprova/rejeita)
```

*   **`red_flags`:** detecta por regra em Python (não pelo LLM) os Sintomas de Risco Imediato — dor torácica, dificuldade respiratória grave, perda de consciência, sangramento massivo e suspeita de AVC — e força a classificação **VERMELHO**. Sintomas negados ("nega dor no peito") são ignorados.
*   **`agent`:** o LLM recebe o system prompt + um bloco com o estado estruturado já apurado (sinais de alarme, idade, sinais vitais, NEWS2).
*   **`tools`:** executa as ferramentas; erros de validação voltam ao LLM para que ele pergunte ao enfermeiro.
*   **`registrar_resultados`:** copia os resultados numéricos das ferramentas para o estado (`idade`, `sinais_vitais`, `escore_news2`, `classificacao`). A classificação final é sempre **a mais grave** entre NEWS2 e sinais de alarme.
*   **`aprovacao_humana`:** *human-in-the-loop* com `interrupt` do LangGraph. Ações que afetam o mundo real só rodam após o enfermeiro aprovar na interface.

## 🏥 Painel do Plantão

A aplicação abre na página **Plantão**, pensada para quem assume o turno:

*   **Indicadores:** pacientes na fila (por cor), maior espera, leitos livres e médicos disponíveis.
*   **Fila de pacientes:** montada a partir das triagens feitas no app, da mais grave para a menos grave, com tempo de espera e alerta quando passa da meta (vermelho: imediato · amarelo: 60 min · verde: 120 min, configurável em `core/fila.py`). Cada paciente pode ser **aberto** na triagem ou marcado como **atendido**.
*   **Pendências:** autorizações aguardando o enfermeiro, vermelhos sem equipe acionada, esperas acima da meta, alas lotadas e especialistas indisponíveis.
*   **Mapa do hospital:** planta com a sala de espera, cada ala e o centro cirúrgico. Cada leito aparece livre ou colorido pela gravidade do internado (passe o mouse para ver paciente, motivo e médico), e cada médico aparece na ala onde está, com o status (disponível, em atendimento, em cirurgia). Dados simulados em `core/hospital.py`, os mesmos usados pelas ferramentas do agente.

O painel se atualiza sozinho a cada 30 segundos. A fila vive na memória do servidor: reiniciar o Streamlit zera os pacientes.

## 🛠️ Ferramentas do Agente (Tools)

1.  `calcular_escore_gravidade`: calcula o **NEWS2** (National Early Warning Score 2) com validação Pydantic (faixas fisiológicas e ACVPU). Se faltar algum dado, **não calcula** e devolve a lista do que falta — o modelo não precisa (nem pode) inventar valores. Para **menores de 16 anos**, informa que o escore adulto não se aplica.
2.  `consultar_leitos`: simula a consulta de vagas por ala (UTI, Enfermarias, Emergência).
3.  `buscar_medico_plantao`: consulta a escala e retorna o especialista de plantão e seu ramal.
4.  `buscar_protocolo_interno`: base simulada de protocolos (Dor Torácica, Sepse, AVC, Pediátrico).
5.  `acionar_equipe_emergencia`: aciona o código vermelho. **Exige aprovação do enfermeiro.**

### Regras do NEWS2

Dados exigidos: idade, FR, SpO₂, oxigênio suplementar (sim/não), PA sistólica, FC, consciência e temperatura.

| Parâmetro | 3 | 2 | 1 | 0 | 1 | 2 | 3 |
|---|---|---|---|---|---|---|---|
| FR (irpm) | ≤8 | | 9–11 | 12–20 | | 21–24 | ≥25 |
| SpO₂ (%) — escala 1 | ≤91 | 92–93 | 94–95 | ≥96 | | | |
| Oxigênio suplementar | | Sim | | Ar ambiente | | | |
| PA sistólica (mmHg) | ≤90 | 91–100 | 101–110 | 111–219 | | | ≥220 |
| FC (bpm) | ≤40 | | 41–50 | 51–90 | 91–110 | 111–130 | ≥131 |
| Consciência (ACVPU) | | | | Alerta | | | Confuso, Voz, Dor ou Inconsciente |
| Temperatura (°C) | ≤35,0 | | 35,1–36,0 | 36,1–38,0 | 38,1–39,0 | ≥39,1 | |

**Classificação:** VERMELHO se escore ≥ 7 ou inconsciente · AMARELO se escore 5–6 ou algum parâmetro isolado com 3 pontos · VERDE nos demais casos.

**Idade:** o NEWS2 não é validado para menores de 16 anos. Nesses casos o agente não classifica por escore: indica o protocolo pediátrico e o pediatra de plantão (os sinais de alarme continuam valendo).

**Limitações conhecidas:** a escala 2 de SpO₂ (DPOC com retenção de CO₂) e a gestação não são tratadas.

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

### 6. Rode os testes
Os testes usam um LLM falso, então não precisam de chave de API nem de internet:
```bash
pytest
```

## 🔒 Regras de Segurança (System Prompt)
O agente foi instruído estritamente para:
- **Nunca** inventar diagnósticos médicos.
- Solicitar informações ausentes de sinais vitais antes de acionar a calculadora de risco.
- Basear o encaminhamento **apenas** no retorno matemático das funções Python, isolando o raciocínio clínico da inferência do LLM.
- **Nunca** rebaixar uma classificação calculada pelo sistema.

Além do prompt, as regras críticas são garantidas **em código**: detecção de sinais de alarme, validação dos sinais vitais, combinação das classificações e aprovação humana para ações sensíveis.

---
*Desenvolvido como projeto de estudo prático sobre Agentes Autônomos em Saúde.*