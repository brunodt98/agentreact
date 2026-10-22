"""
Blocos visuais da interface (cabeçalho, faixa de classificação, cartões de sinais vitais).
Cada função devolve uma string HTML; o app.py renderiza com st.html.
Todo texto que pode vir do LLM ou do usuário passa por html.escape.
"""
from base64 import b64encode
from html import escape
from pathlib import Path

# --- 1. PALETA E METADADOS ---

NIVEIS = {
    "VERMELHO": {"titulo": "Emergência", "descricao": "Atendimento imediato", "cor": "#DC2626", "fundo": "#FEF2F2"},
    "AMARELO": {"titulo": "Urgência", "descricao": "Avaliação médica rápida", "cor": "#D97706", "fundo": "#FFFBEB"},
    "VERDE": {"titulo": "Pouco urgente", "descricao": "Fluxo padrão de atendimento", "cor": "#16A34A", "fundo": "#F0FDF4"},
}

# Cor por pontuação do parâmetro no NEWS2 (0 = normal ... 3 = crítico)
CORES_PONTOS = {
    0: ("#16A34A", "#F0FDF4", "Normal"),
    1: ("#CA8A04", "#FEFCE8", "+1 ponto"),
    2: ("#EA580C", "#FFF7ED", "+2 pontos"),
    3: ("#DC2626", "#FEF2F2", "+3 pontos"),
}

# Ordem do NEWS2: campo -> (rótulo, unidade)
SINAIS_VITAIS = {
    "frequencia_respiratoria": ("Freq. respiratória", "irpm"),
    "saturacao_o2": ("Saturação O₂", "%"),
    "oxigenio_suplementar": ("Oxigênio", ""),
    "pressao_sistolica": ("PA sistólica", "mmHg"),
    "frequencia_cardiaca": ("Freq. cardíaca", "bpm"),
    "nivel_consciencia": ("Consciência", ""),
    "temperatura": ("Temperatura", "°C"),
}

# Nome amigável e ícone (Material Symbols) de cada ferramenta do agente
FERRAMENTAS = {
    "calcular_escore_gravidade": ("Escore NEWS2", ":material/calculate:"),
    "consultar_leitos": ("Consulta de leitos", ":material/bed:"),
    "buscar_medico_plantao": ("Médico de plantão", ":material/stethoscope:"),
    "buscar_protocolo_interno": ("Protocolo interno", ":material/menu_book:"),
    "acionar_equipe_emergencia": ("Acionamento da emergência", ":material/emergency:"),
}

ROTULOS_ARGUMENTOS = {
    "idade": "Idade",
    **{campo: rotulo for campo, (rotulo, _) in SINAIS_VITAIS.items()},
    "ala": "Ala",
    "especialidade": "Especialidade",
    "sintoma_ou_condicao": "Condição",
    "motivo": "Motivo",
}

# --- 2. CSS GLOBAL ---
# Atenção: não use o caractere "<" dentro do CSS (nem em comentários). O st.html filtra o conteúdo
# com DOMPurify, que descarta o bloco <style> inteiro nesse caso.

CSS = """
<style>
:root {
  --tr-ink: #0F172A; --tr-muted: #64748B; --tr-line: #E2E8F0; --tr-card: #FFFFFF;
  --tr-brand: #0E7490; --tr-brand-soft: #ECFEFF;
}
.block-container { padding-top: 3.6rem; max-width: 1360px; }
[data-testid="stHeader"] { background: transparent; }

/* Chat e painel rolam por dentro e ocupam a altura da tela: o cabeçalho e a faixa de risco ficam sempre visíveis */
/* O Streamlit fixa a altura no pai do container e usa flex-basis 0, por isso o :has e o flex: none */
@media (min-width: 900px) {
  div:has(> .st-key-historico), .st-key-historico { height: max(260px, calc(100vh - 452px)) !important; flex: none !important; }
  div:has(> .st-key-painel), .st-key-painel { height: max(400px, calc(100vh - 290px)) !important; flex: none !important; }
}
@media (max-width: 899px) {
  div:has(> .st-key-historico), div:has(> .st-key-painel),
  .st-key-historico, .st-key-painel { height: auto !important; flex: none !important; overflow: visible !important; }
}
[data-testid="stSidebarContent"] { padding-top: .5rem; }

.tr-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.tr-brand { display: flex; align-items: center; gap: 14px; }
.tr-logo { width: 42px; height: 42px; border-radius: 11px; background: var(--tr-brand);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.tr-title { font-weight: 700; font-size: 1.15rem; color: var(--tr-ink); line-height: 1.25; }
.tr-sub { font-size: .82rem; color: var(--tr-muted); }
.tr-meta { display: flex; gap: 8px; flex-wrap: wrap; }
.tr-pill { font-size: .78rem; font-weight: 500; color: #334155; background: #F1F5F9; border-radius: 999px;
  padding: 4px 11px; font-variant-numeric: tabular-nums; white-space: nowrap; }

.tr-banner { display: flex; border-radius: 14px; overflow: hidden; border: 1px solid var(--tr-line); margin-top: 2px; }
.tr-banner-bar { width: 8px; flex-shrink: 0; }
.tr-banner-body { flex: 1; padding: 12px 22px; display: flex; justify-content: space-between; align-items: center;
  gap: 16px; flex-wrap: wrap; }
.tr-eyebrow { font-size: .72rem; font-weight: 600; color: var(--tr-muted); text-transform: uppercase; letter-spacing: .08em; }
.tr-level { font-size: 1.5rem; font-weight: 700; letter-spacing: .01em; line-height: 1.2; }
.tr-level-desc { color: #334155; font-weight: 500; font-size: .92rem; }
.tr-score { text-align: right; min-width: 90px; }
.tr-score-num { font-size: 2.4rem; font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
.tr-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.tr-chip { font-size: .76rem; font-weight: 600; border-radius: 999px; padding: 3px 10px; white-space: nowrap; }

.tr-section { display: flex; align-items: baseline; justify-content: space-between; margin: 2px 0 10px; }
.tr-vitals { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.tr-vital { background: var(--tr-card); border: 1px solid var(--tr-line); border-left: 4px solid #CBD5E1;
  border-radius: 12px; padding: 10px 12px; }
.tr-vital.pendente { border: 1px dashed #CBD5E1; background: #F8FAFC; }
.tr-vital-lbl { font-size: .7rem; font-weight: 600; color: var(--tr-muted); text-transform: uppercase; letter-spacing: .06em; }
.tr-vital-val { font-size: 1.3rem; font-weight: 700; color: var(--tr-ink); font-variant-numeric: tabular-nums;
  margin-top: 2px; line-height: 1.3; }
.tr-vital-val small { font-size: .74rem; font-weight: 500; color: var(--tr-muted); margin-left: 3px; }
.tr-vital.pendente .tr-vital-val { color: #94A3B8; font-weight: 500; font-size: 1rem; }
.tr-badge { display: inline-block; font-size: .68rem; font-weight: 600; border-radius: 6px; padding: 1px 7px; margin-top: 5px; }

/* --- Chat estilo aplicativo de mensagens --- */
.st-key-chatcard { background: var(--tr-card); border: 1px solid var(--tr-line); border-radius: 16px;
  gap: 0 !important; overflow: hidden; box-shadow: 0 1px 3px rgba(15, 23, 42, .04); }
.tr-chat-head { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-bottom: 1px solid var(--tr-line); }
.tr-chat-avatar { width: 46px; height: 46px; border-radius: 50%; flex-shrink: 0; box-shadow: 0 0 0 3px #CFFAFE; }
.tr-chat-name { font-weight: 700; color: var(--tr-ink); font-size: 1rem; line-height: 1.2; }
.tr-chat-status { font-size: .78rem; color: var(--tr-muted); display: flex; align-items: center; gap: 6px; }
.tr-online { width: 8px; height: 8px; border-radius: 50%; background: #22C55E; box-shadow: 0 0 0 3px #DCFCE7; }
.tr-chat-tag { margin-left: auto; font-size: .72rem; font-weight: 600; color: var(--tr-brand); background: var(--tr-brand-soft);
  border: 1px solid #A5F3FC; border-radius: 999px; padding: 3px 10px; white-space: nowrap; }

.st-key-historico { background-color: #F8FAFC; padding: 14px 16px !important; gap: 12px !important;
  background-image: radial-gradient(#E2E8F0 1px, transparent 1px); background-size: 18px 18px; }
.st-key-entrada { padding: 10px 14px 12px; border-top: 1px solid var(--tr-line); }

/* Balões: assistente à esquerda (branco), enfermeiro à direita (azul-petróleo).
   O Streamlit põe margem lateral no balão; não mexa na margem dos parágrafos: o markdown a compensa com margem negativa. */
[data-testid="stChatMessage"] { background: transparent !important; padding: 0 !important; gap: 10px; align-items: flex-start; }
[data-testid="stChatMessageAvatarImage"] { width: 36px; height: 36px; border-radius: 50%; }
[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] { flex: 0 1 auto; width: fit-content; max-width: 82%;
  margin: 0 !important; padding: 10px 14px; box-shadow: 0 1px 2px rgba(15, 23, 42, .06); }
[data-testid="stChatMessage"]:has([aria-label="Chat message from assistant"]) [data-testid="stChatMessageContent"] {
  background: #FFFFFF; border: 1px solid var(--tr-line); border-radius: 4px 16px 16px 16px; }
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) { flex-direction: row-reverse; }
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) [data-testid="stChatMessageContent"] {
  background: var(--tr-brand); border-radius: 16px 4px 16px 16px; }
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) [data-testid="stChatMessageContent"] p { color: #FFFFFF; }

/* Consultas que o assistente fez: pílulas discretas abaixo do balão */
.tr-tools { display: flex; flex-wrap: wrap; gap: 6px; margin-left: 46px; }
.tr-tool { display: inline-flex; align-items: center; gap: 6px; font-size: .74rem; font-weight: 600; color: #0F766E;
  background: #F0FDFA; border: 1px solid #99F6E4; border-radius: 999px; padding: 3px 10px; }
.tr-tool.erro { color: #B45309; background: #FFFBEB; border-color: #FDE68A; }
[class*="st-key-detalhes_"] { margin-left: 46px; width: auto !important; }
[class*="st-key-detalhes_"] details { border-radius: 10px; background: #FFFFFF; }
[class*="st-key-detalhes_"] summary { padding-top: 4px; padding-bottom: 4px; font-size: .8rem; }

/* Indicador "digitando" */
.tr-typing { display: flex; align-items: center; gap: 8px; color: var(--tr-muted); font-size: .85rem; }
.tr-typing span { width: 7px; height: 7px; border-radius: 50%; background: #22D3EE; animation: tr-pulo 1.2s infinite ease-in-out; }
.tr-typing span:nth-child(2) { animation-delay: .15s; }
.tr-typing span:nth-child(3) { animation-delay: .3s; }
@keyframes tr-pulo { 0%, 80%, 100% { transform: translateY(0); opacity: .5; } 40% { transform: translateY(-5px); opacity: 1; } }

/* Saudação e casos de exemplo */
.tr-hello { color: #334155; }
.tr-hello b { color: var(--tr-ink); }
.tr-hello ol { margin: 6px 0 0; padding-left: 18px; font-size: .9rem; }
.tr-hello li { margin: 2px 0; }
.st-key-exemplos { margin-left: 46px; width: auto !important; }
.st-key-exemplos button { border-radius: 999px !important; border: 1px solid #A5F3FC !important; background: var(--tr-brand-soft) !important;
  color: var(--tr-brand) !important; min-height: 34px; }
.st-key-exemplos button:hover { background: #CFFAFE !important; }
@media (max-width: 640px) { .tr-score { text-align: left; } .tr-tools, .st-key-exemplos, [class*="st-key-detalhes_"] { margin-left: 0; } }

.tr-legend { display: flex; flex-direction: column; gap: 8px; font-size: .85rem; color: #334155; }
.tr-legend-row { display: flex; align-items: center; gap: 10px; }
.tr-dot { width: 12px; height: 12px; border-radius: 4px; flex-shrink: 0; }
.tr-disclaimer { font-size: .75rem; color: var(--tr-muted); line-height: 1.45; border-top: 1px solid var(--tr-line); padding-top: 12px; }

.st-key-aprovacao { border: 2px solid #DC2626 !important; background: #FEF2F2; border-radius: 14px; }
.tr-approval-title { font-weight: 700; color: #991B1B; font-size: 1rem; }
.tr-approval-item { background: #FFFFFF; border: 1px solid #FECACA; border-radius: 10px; padding: 10px 14px; margin-top: 8px;
  font-size: .9rem; color: #334155; }
.tr-approval-item b { color: var(--tr-ink); }
</style>
"""

# Ícone de "monitor cardíaco" (linha de ECG) do cabeçalho. Vai como imagem em data URI
# porque o st.html remove <svg> embutido.
_LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
    'stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M3 12h4l2-5 4 10 2-5h6"/></svg>'
)
_LOGO = f'<img alt="" width="24" height="24" src="data:image/svg+xml;base64,{b64encode(_LOGO_SVG.encode()).decode()}">'

NOME_ASSISTENTE = "Clara"

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
AVATAR_ASSISTENTE = str(_ASSETS / "assistente.png")
AVATAR_ENFERMEIRO = str(_ASSETS / "enfermeiro.png")
_AVATAR_URI = "data:image/png;base64," + b64encode((_ASSETS / "assistente.png").read_bytes()).decode()

# --- 3. COMPONENTES ---


def cabecalho(titulo: str, subtitulo: str, pilulas: list[str]) -> str:
    pilulas_html = "".join(f'<span class="tr-pill">{escape(p)}</span>' for p in pilulas)
    return (
        '<div class="tr-header">'
        f'<div class="tr-brand"><div class="tr-logo">{_LOGO}</div>'
        f'<div><div class="tr-title">{escape(titulo)}</div>'
        f'<div class="tr-sub">{escape(subtitulo)}</div></div></div>'
        f'<div class="tr-meta">{pilulas_html}</div></div>'
    )


def _chip(texto: str, cor: str, fundo: str) -> str:
    return f'<span class="tr-chip" style="color:{cor};background:{fundo}">{escape(texto)}</span>'


def faixa_classificacao(estado: dict) -> str:
    """Faixa colorida no topo: nível de risco, escore NEWS2 e sinais de alarme."""
    classificacao = estado.get("classificacao")
    nao_aplicavel = estado.get("escore_nao_aplicavel")

    if classificacao in NIVEIS:
        nivel = NIVEIS[classificacao]
        cor, fundo = nivel["cor"], nivel["fundo"]
        titulo = f'<div class="tr-level" style="color:{cor}">{classificacao} · {nivel["titulo"]}</div>'
        descricao = nivel["descricao"]
    elif nao_aplicavel:
        cor, fundo = "#2563EB", "#EFF6FF"
        titulo = f'<div class="tr-level" style="color:{cor}">Paciente pediátrico</div>'
        descricao = "NEWS2 não se aplica · classificar pela avaliação clínica e protocolo pediátrico"
    else:
        cor, fundo = "#94A3B8", "#FFFFFF"
        titulo = '<div class="tr-level" style="color:#475569">Aguardando dados</div>'
        descricao = "Informe idade, sintomas e sinais vitais no chat para iniciar a classificação"

    chips = [_chip(f"Sinal de alarme: {flag}", "#B91C1C", "#FEE2E2") for flag in estado.get("red_flags") or []]
    if estado.get("emergencia_acionada"):
        chips.append(_chip("Equipe de emergência acionada", "#FFFFFF", "#DC2626"))
    if estado.get("idade") is not None:
        chips.append(_chip(f"{estado['idade']} anos", "#334155", "#F1F5F9"))
    chips_html = f'<div class="tr-chips">{"".join(chips)}</div>' if chips else ""

    escore = estado.get("escore_news2")
    escore_html = (
        f'<div class="tr-score-num" style="color:{cor if escore is not None else "#CBD5E1"}">'
        f'{escore if escore is not None else "—"}</div>'
    )

    return (
        f'<div class="tr-banner" style="background:{fundo}">'
        f'<div class="tr-banner-bar" style="background:{cor}"></div>'
        '<div class="tr-banner-body">'
        f'<div><div class="tr-eyebrow">Classificação de risco</div>{titulo}'
        f'<div class="tr-level-desc">{escape(descricao)}</div>{chips_html}</div>'
        f'<div class="tr-score"><div class="tr-eyebrow">Escore NEWS2</div>{escore_html}</div>'
        '</div></div>'
    )


def _formatar_valor(campo: str, valor) -> tuple[str, str]:
    """Devolve (valor, unidade) prontos para exibição."""
    rotulo_unidade = SINAIS_VITAIS[campo][1]
    if campo == "oxigenio_suplementar":
        return ("Suplementar" if valor else "Ar ambiente"), ""
    if campo == "temperatura":
        return f"{valor:.1f}".replace(".", ","), rotulo_unidade
    return escape(str(valor)), rotulo_unidade


def cartoes_sinais_vitais(estado: dict) -> str:
    """Grade com um cartão por parâmetro do NEWS2, colorido pela pontuação; pendentes ficam tracejados."""
    sinais = estado.get("sinais_vitais") or {}
    pontos = estado.get("pontos_news2") or {}
    informados = sum(1 for campo in SINAIS_VITAIS if sinais.get(campo) is not None)

    cartoes = []
    for campo, (rotulo, _) in SINAIS_VITAIS.items():
        valor = sinais.get(campo)
        if valor is None:
            cartoes.append(
                f'<div class="tr-vital pendente"><div class="tr-vital-lbl">{rotulo}</div>'
                '<div class="tr-vital-val">Pendente</div></div>'
            )
            continue

        texto, unidade = _formatar_valor(campo, valor)
        unidade_html = f"<small>{unidade}</small>" if unidade else ""
        estilo, badge = "", ""
        if campo in pontos:
            cor, fundo, legenda = CORES_PONTOS[pontos[campo]]
            estilo = f' style="border-left-color:{cor}"'
            badge = f'<span class="tr-badge" style="color:{cor};background:{fundo}">{legenda}</span>'
        cartoes.append(
            f'<div class="tr-vital"{estilo}><div class="tr-vital-lbl">{rotulo}</div>'
            f'<div class="tr-vital-val">{texto}{unidade_html}</div>{badge}</div>'
        )

    return (
        '<div class="tr-section"><span class="tr-eyebrow">Sinais vitais</span>'
        f'<span class="tr-pill">{informados}/{len(SINAIS_VITAIS)} coletados</span></div>'
        f'<div class="tr-vitals">{"".join(cartoes)}</div>'
    )


def cabecalho_chat() -> str:
    return (
        f'<div class="tr-chat-head"><img class="tr-chat-avatar" alt="" src="{_AVATAR_URI}">'
        f'<div><div class="tr-chat-name">{NOME_ASSISTENTE}</div>'
        '<div class="tr-chat-status"><span class="tr-online"></span>Assistente de triagem · online</div></div>'
        '<span class="tr-chat-tag">Protocolo NEWS2</span></div>'
    )


def saudacao() -> str:
    return (
        f'<div class="tr-hello">Olá! Eu sou a <b>{NOME_ASSISTENTE}</b>, assistente de triagem. '
        'Me conte sobre o paciente e eu organizo os dados e calculo o risco.'
        '<ol><li><b>Descreva</b> idade, queixa e os sinais vitais que tiver.</li>'
        '<li>Eu <b>pergunto o que faltar</b> — nunca estimo valores.</li>'
        '<li>Ações como acionar a emergência só acontecem <b>com sua aprovação</b>.</li></ol></div>'
    )


def digitando() -> str:
    return f'<div class="tr-typing"><span></span><span></span><span></span>{NOME_ASSISTENTE} está analisando o caso...</div>'


def pilulas_ferramentas(itens: list[tuple[str, bool]]) -> str:
    """Pílulas 'Escore NEWS2' para as consultas de um passo do agente. itens = [(nome, teve_erro)]."""
    pilulas = "".join(
        f'<span class="tr-tool{" erro" if erro else ""}">{"⚠" if erro else "✓"} {escape(nome)}</span>'
        for nome, erro in itens
    )
    return f'<div class="tr-tools">{pilulas}</div>'


def legenda_classificacao() -> str:
    linhas = "".join(
        f'<div class="tr-legend-row"><span class="tr-dot" style="background:{n["cor"]}"></span>'
        f'<span><b>{nome.title()}</b> · {n["descricao"]}</span></div>'
        for nome, n in NIVEIS.items()
    )
    return f'<div class="tr-legend">{linhas}</div>'


def aviso_legal() -> str:
    return (
        '<div class="tr-disclaimer">Ferramenta de apoio à decisão para uso por profissionais de saúde. '
        'Não substitui a avaliação clínica. Dados de leitos, escalas e protocolos são simulados.</div>'
    )


def itens_aprovacao(acoes: list[dict]) -> str:
    """Descreve em linguagem clara cada ação que aguarda aprovação."""
    itens = []
    for acao in acoes:
        nome, _ = FERRAMENTAS.get(acao["ferramenta"], (acao["ferramenta"], ""))
        detalhes = "".join(
            f"<div><b>{escape(ROTULOS_ARGUMENTOS.get(k, k))}:</b> {escape(str(v))}</div>"
            for k, v in acao.get("argumentos", {}).items()
        )
        itens.append(f'<div class="tr-approval-item"><div><b>{escape(nome)}</b></div>{detalhes}</div>')
    return "".join(itens)


def formatar_argumentos(argumentos: dict) -> str:
    """Lista 'Rótulo: valor' em markdown para o detalhe de uma ferramenta."""
    if not argumentos:
        return "_Sem parâmetros._"
    linhas = []
    for chave, valor in argumentos.items():
        if isinstance(valor, bool):
            valor = "Sim" if valor else "Não"
        linhas.append(f"- **{ROTULOS_ARGUMENTOS.get(chave, chave)}:** {valor}")
    return "\n".join(linhas)
