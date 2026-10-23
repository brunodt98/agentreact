"""
Blocos visuais da interface (cabeçalho, resumo do paciente, sinais vitais, chat).
Cada função devolve uma string HTML; as páginas renderizam com st.html.
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
    0: ("#94A3B8", "transparent", "Normal"),
    1: ("#CA8A04", "#FEFCE8", "+1"),
    2: ("#EA580C", "#FFF7ED", "+2"),
    3: ("#DC2626", "#FEF2F2", "+3"),
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
  --tr-ink: #0F172A; --tr-text: #334155; --tr-muted: #64748B; --tr-faint: #94A3B8;
  --tr-line: #E8EDF3; --tr-card: #FFFFFF; --tr-soft: #F6F8FB;
  --tr-brand: #0E7490; --tr-brand-soft: #ECFEFF;
  --tr-shadow: 0 1px 2px rgba(15, 23, 42, .04), 0 4px 16px rgba(15, 23, 42, .04);
}
.block-container { padding: 3.4rem 2rem 1rem; max-width: 1760px; }
[data-testid="stHeader"] { background: transparent; }

/* Cabeçalho da página: título à esquerda, ações à direita */
.tr-header { display: flex; align-items: center; gap: 12px; }
.tr-logo { width: 38px; height: 38px; border-radius: 10px; background: var(--tr-brand);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.tr-title { font-weight: 700; font-size: 1.2rem; color: var(--tr-ink); line-height: 1.2; }
.tr-sub { font-size: .84rem; color: var(--tr-muted); font-variant-numeric: tabular-nums; }

/* Cartões brancos usados nas duas páginas */
.tr-card { background: var(--tr-card); border: 1px solid var(--tr-line); border-radius: 16px;
  padding: 16px 18px; box-shadow: var(--tr-shadow); }
.tr-card + .tr-card { margin-top: 12px; }
.tr-card-title { display: flex; align-items: center; justify-content: space-between; gap: 8px;
  font-size: .9rem; font-weight: 600; color: var(--tr-ink); margin-bottom: 10px; }
.tr-count { font-size: .78rem; font-weight: 500; color: var(--tr-muted); font-variant-numeric: tabular-nums; }

/* Altura das colunas acompanha a tela; chat e painel rolam por dentro */
@media (min-width: 900px) {
  div:has(> .st-key-historico), .st-key-historico { height: max(300px, calc(100vh - 262px)) !important; flex: none !important; }
  div:has(> .st-key-painel), .st-key-painel { height: max(360px, calc(100vh - 150px)) !important; flex: none !important; }
}
@media (max-width: 899px) {
  div:has(> .st-key-historico), div:has(> .st-key-painel),
  .st-key-historico, .st-key-painel { height: auto !important; flex: none !important; overflow: visible !important; }
}

/* --- Resumo do paciente (nível de risco + NEWS2) --- */
.tr-risk { display: flex; align-items: center; gap: 14px; }
.tr-risk-icon { width: 46px; height: 46px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center;
  justify-content: center; }
.tr-risk-icon span { width: 16px; height: 16px; border-radius: 50%; }
.tr-risk-text { flex: 1; min-width: 0; }
.tr-level { font-size: 1.25rem; font-weight: 700; line-height: 1.2; }
.tr-level-desc { color: var(--tr-muted); font-size: .86rem; margin-top: 1px; }
.tr-score { text-align: center; min-width: 64px; }
.tr-score-num { font-size: 1.9rem; font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
.tr-score-lbl { font-size: .72rem; font-weight: 600; color: var(--tr-muted); margin-top: 3px; }
.tr-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 12px; }
.tr-chip { font-size: .76rem; font-weight: 600; border-radius: 999px; padding: 3px 10px; white-space: nowrap; }

/* --- Sinais vitais: lista compacta --- */
.tr-progress { height: 4px; border-radius: 2px; background: #EEF2F6; overflow: hidden; margin: -2px 0 6px; }
.tr-progress div { height: 100%; background: var(--tr-brand); border-radius: 2px; }
.tr-vrow { display: flex; align-items: center; gap: 10px; padding: 9px 0; border-bottom: 1px solid #F1F4F8; }
.tr-vrow:last-child { border-bottom: 0; padding-bottom: 0; }
.tr-vlbl { flex: 1; font-size: .88rem; color: var(--tr-text); }
.tr-vval { font-size: .98rem; font-weight: 600; color: var(--tr-ink); font-variant-numeric: tabular-nums; }
.tr-vval small { font-size: .75rem; font-weight: 500; color: var(--tr-muted); margin-left: 2px; }
.tr-vval.pendente { color: #CBD5E1; font-weight: 500; }
.tr-pts { font-size: .72rem; font-weight: 700; border-radius: 6px; padding: 2px 7px; min-width: 50px; text-align: center; }
.tr-pts.vazio { visibility: hidden; }

/* --- Recursos agora: leitos e médicos, em duas colunas --- */
.tr-res { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr); gap: 4px 28px; }
@media (max-width: 1300px) { .tr-res { grid-template-columns: minmax(0, 1fr); } }
.tr-res-head { font-size: .76rem; color: var(--tr-muted); margin-bottom: 2px; }
.tr-res-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 6px 0;
  border-bottom: 1px solid #F1F4F8; font-size: .86rem; color: var(--tr-text); }
.tr-res-row:last-child { border-bottom: 0; }
.tr-res-row b { font-variant-numeric: tabular-nums; }
.tr-res-st { display: inline-flex; align-items: center; gap: 6px; font-size: .8rem; white-space: nowrap; }
.tr-res-st .tr-dot { width: 8px; height: 8px; }

/* --- Chat --- */
.st-key-chatcard { background: var(--tr-card); border: 1px solid var(--tr-line); border-radius: 16px;
  gap: 0 !important; overflow: hidden; box-shadow: var(--tr-shadow); }
.st-key-historico { padding: 18px 18px 8px !important; gap: 14px !important; }
.st-key-entrada { padding: 8px 14px 14px; }
.st-key-entrada [data-testid="stChatInput"] { border-radius: 14px; background: var(--tr-soft); }

/* Balões: assistente à esquerda (cinza claro), enfermeiro à direita (azul-petróleo).
   O Streamlit põe margem lateral no balão; não mexa na margem dos parágrafos: o markdown a compensa com margem negativa. */
[data-testid="stChatMessage"] { background: transparent !important; padding: 0 !important; gap: 10px; align-items: flex-start; }
[data-testid="stChatMessageAvatarImage"] { width: 32px; height: 32px; border-radius: 50%; }
[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] { flex: 0 1 auto; width: fit-content; max-width: 85%;
  margin: 0 !important; padding: 10px 14px; }
[data-testid="stChatMessage"]:has([aria-label="Chat message from assistant"]) [data-testid="stChatMessageContent"] {
  background: #F1F5F9; border-radius: 4px 16px 16px 16px; }
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) { flex-direction: row-reverse; }
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) [data-testid="stChatMessageContent"] {
  background: var(--tr-brand); border-radius: 16px 4px 16px 16px; }
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) [data-testid="stChatMessageContent"] p { color: #FFFFFF; }

/* Consultas do assistente: uma linha discreta que abre os detalhes */
[class*="st-key-detalhes_"] { margin-left: 42px; width: auto !important; }
[class*="st-key-detalhes_"] details { border: 0; background: transparent; }
[class*="st-key-detalhes_"] summary { padding: 2px 0; font-size: .8rem; color: var(--tr-muted); min-height: 0; }
[class*="st-key-detalhes_"] summary:hover { color: var(--tr-brand); }
[class*="st-key-detalhes_"] [data-testid="stExpanderDetails"] { background: var(--tr-soft); border-radius: 10px;
  padding: 10px 14px; font-size: .85rem; }

/* Indicador "digitando" */
.tr-typing { display: flex; align-items: center; gap: 8px; color: var(--tr-muted); font-size: .85rem; }
.tr-typing span { width: 7px; height: 7px; border-radius: 50%; background: #22D3EE; animation: tr-pulo 1.2s infinite ease-in-out; }
.tr-typing span:nth-child(2) { animation-delay: .15s; }
.tr-typing span:nth-child(3) { animation-delay: .3s; }
@keyframes tr-pulo { 0%, 80%, 100% { transform: translateY(0); opacity: .5; } 40% { transform: translateY(-5px); opacity: 1; } }

/* Saudação e casos de exemplo */
.tr-hello { color: var(--tr-text); }
.tr-hello b { color: var(--tr-ink); }
.tr-hello ul { margin: 6px 0 0; padding-left: 18px; font-size: .9rem; }
.tr-hello li { margin: 2px 0; }
.st-key-exemplos { margin-left: 42px; width: auto !important; }
.st-key-exemplos [data-testid="stCaptionContainer"] { margin-bottom: -4px; }
.st-key-exemplos button { border-radius: 999px !important; border: 1px solid var(--tr-line) !important; background: #FFFFFF !important;
  color: var(--tr-text) !important; min-height: 34px; font-size: .86rem; }
.st-key-exemplos button:hover { border-color: var(--tr-brand) !important; color: var(--tr-brand) !important; }

/* Autorização: aparece no fim da conversa, logo abaixo da pergunta da assistente */
.st-key-aprovacao { margin-left: 42px; width: auto !important; background: #FFFBEB; border: 1px solid #FDE68A !important;
  border-radius: 14px; padding: 14px 16px 4px !important; }
.tr-approval-title { font-weight: 700; color: #92400E; font-size: .95rem; }
.tr-approval-sub { font-size: .84rem; color: #92400E; opacity: .85; }
.tr-approval-item { background: #FFFFFF; border: 1px solid #FDE68A; border-radius: 10px; padding: 10px 14px; margin-top: 10px;
  font-size: .88rem; color: var(--tr-text); }
.tr-approval-item b { color: var(--tr-ink); }

/* Ajuda (popover do cabeçalho) */
.tr-legend { display: flex; flex-direction: column; gap: 8px; font-size: .88rem; color: var(--tr-text); }
.tr-legend-row { display: flex; align-items: center; gap: 10px; }
.tr-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.tr-help { font-size: .88rem; color: var(--tr-text); }
.tr-help ul { margin: 4px 0 0; padding-left: 18px; }
.tr-help li { margin: 4px 0; }
.tr-disclaimer { font-size: .76rem; color: var(--tr-faint); line-height: 1.45; margin-top: 10px; }
@media (max-width: 640px) { [class*="st-key-detalhes_"], .st-key-exemplos, .st-key-aprovacao { margin-left: 0; } }
</style>
"""

# Ícone de "monitor cardíaco" (linha de ECG) do cabeçalho. Vai como imagem em data URI
# porque o st.html remove <svg> embutido.
_LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" '
    'stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M3 12h4l2-5 4 10 2-5h6"/></svg>'
)
_LOGO = f'<img alt="" width="22" height="22" src="data:image/svg+xml;base64,{b64encode(_LOGO_SVG.encode()).decode()}">'

NOME_ASSISTENTE = "Clara"

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
AVATAR_ASSISTENTE = str(_ASSETS / "assistente.png")
AVATAR_ENFERMEIRO = str(_ASSETS / "enfermeiro.png")

# --- 3. COMPONENTES ---


def cabecalho(titulo: str, detalhe: str) -> str:
    return (
        f'<div class="tr-header"><div class="tr-logo">{_LOGO}</div>'
        f'<div><div class="tr-title">{escape(titulo)}</div>'
        f'<div class="tr-sub">{escape(detalhe)}</div></div></div>'
    )


def _chip(texto: str, cor: str, fundo: str) -> str:
    return f'<span class="tr-chip" style="color:{cor};background:{fundo}">{escape(texto)}</span>'


def resumo_paciente(estado: dict) -> str:
    """Cartão do topo do painel: nível de risco, escore NEWS2, idade e alertas."""
    classificacao = estado.get("classificacao")
    red_flags = estado.get("red_flags") or []
    emergencia = estado.get("emergencia_acionada")

    if classificacao in NIVEIS:
        nivel = NIVEIS[classificacao]
        cor, fundo = nivel["cor"], nivel["fundo"]
        titulo, descricao = f'{classificacao.title()} · {nivel["titulo"]}', nivel["descricao"]
    elif estado.get("escore_nao_aplicavel"):
        cor, fundo = "#2563EB", "#EFF6FF"
        titulo, descricao = "Paciente pediátrico", "NEWS2 não se aplica · siga a avaliação clínica"
    elif red_flags or emergencia or estado.get("idade") is not None:
        # Já há dados (ou até a emergência acionada), mas o escore ainda não foi calculado
        cor, fundo = "#475569", "#F1F5F9"
        titulo, descricao = "Em avaliação", "Faltam sinais vitais para calcular o NEWS2"
    else:
        cor, fundo = "#94A3B8", "#F1F5F9"
        titulo, descricao = "Aguardando dados", "Descreva o paciente no chat para começar"

    chips = []
    if emergencia:
        chips.append(_chip("Equipe de emergência acionada", "#FFFFFF", "#DC2626"))
    chips += [_chip(f"Sinal de alarme: {flag}", "#B91C1C", "#FEE2E2") for flag in red_flags]
    if estado.get("idade") is not None:
        chips.append(_chip(f"{estado['idade']} anos", "#334155", "#F1F5F9"))
    chips_html = f'<div class="tr-chips">{"".join(chips)}</div>' if chips else ""

    escore = estado.get("escore_news2")
    escore_html = (
        f'<div class="tr-score"><div class="tr-score-num" style="color:{cor if escore is not None else "#CBD5E1"}">'
        f'{escore if escore is not None else "–"}</div><div class="tr-score-lbl">NEWS2</div></div>'
    )
    cor_titulo = cor if classificacao in NIVEIS else "#0F172A"

    return (
        f'<div class="tr-card" style="border-top:4px solid {cor}">'
        f'<div class="tr-risk"><div class="tr-risk-icon" style="background:{fundo}"><span style="background:{cor}"></span></div>'
        f'<div class="tr-risk-text"><div class="tr-level" style="color:{cor_titulo}">{escape(titulo)}</div>'
        f'<div class="tr-level-desc">{escape(descricao)}</div></div>{escore_html}</div>'
        f'{chips_html}</div>'
    )


def _formatar_valor(campo: str, valor) -> tuple[str, str]:
    """Devolve (valor, unidade) prontos para exibição."""
    unidade = SINAIS_VITAIS[campo][1]
    if campo == "oxigenio_suplementar":
        return ("Suplementar" if valor else "Ar ambiente"), ""
    if campo == "temperatura":
        return f"{valor:.1f}".replace(".", ","), unidade
    return escape(str(valor)), unidade


def sinais_vitais(estado: dict) -> str:
    """Lista dos 7 parâmetros do NEWS2 com a pontuação de cada um; pendentes aparecem com traço."""
    sinais = estado.get("sinais_vitais") or {}
    pontos = estado.get("pontos_news2") or {}
    informados = sum(1 for campo in SINAIS_VITAIS if sinais.get(campo) is not None)

    linhas = []
    for campo, (rotulo, _) in SINAIS_VITAIS.items():
        valor = sinais.get(campo)
        if valor is None:
            valor_html, badge = '<span class="tr-vval pendente">–</span>', '<span class="tr-pts vazio"></span>'
        else:
            texto, unidade = _formatar_valor(campo, valor)
            unidade_html = f"<small>{unidade}</small>" if unidade else ""
            valor_html = f'<span class="tr-vval">{texto}{unidade_html}</span>'
            badge = '<span class="tr-pts vazio"></span>'
            if campo in pontos:
                cor, fundo, legenda = CORES_PONTOS[pontos[campo]]
                badge = f'<span class="tr-pts" style="color:{cor};background:{fundo}">{legenda}</span>'
        linhas.append(f'<div class="tr-vrow"><span class="tr-vlbl">{rotulo}</span>{valor_html}{badge}</div>')

    progresso = round(100 * informados / len(SINAIS_VITAIS))
    return (
        '<div class="tr-card"><div class="tr-card-title">Sinais vitais'
        f'<span class="tr-count">{informados} de {len(SINAIS_VITAIS)} coletados</span></div>'
        f'<div class="tr-progress"><div style="width:{progresso}%"></div></div>'
        f'{"".join(linhas)}</div>'
    )


_COR_STATUS_MEDICO = {"Disponível": "#16A34A", "Em atendimento": "#D97706", "Em cirurgia": "#DC2626"}


def recursos_hospital(leitos: dict, escala: dict) -> str:
    """Leitos livres por ala e médicos de plantão: ajuda a decidir para onde o paciente vai."""
    alas = []
    for ala, l in leitos.items():
        livres = l["total"] - l["ocupados"]
        cor = "#DC2626" if livres == 0 else ("#D97706" if livres / l["total"] <= 0.2 else "#0F172A")
        alas.append(f'<div class="tr-res-row"><span>{escape(ala)}</span>'
                    f'<b style="color:{cor}">{livres if livres else "Lotada"}</b></div>')
    medicos = []
    for especialidade, m in escala.items():
        cor = _COR_STATUS_MEDICO.get(m["status"], "#64748B")
        medicos.append(f'<div class="tr-res-row" title="{escape(m["nome"])} · ramal {escape(m["ramal"])}">'
                       f'<span>{escape(especialidade)}</span><span class="tr-res-st">'
                       f'<span class="tr-dot" style="background:{cor}"></span>{escape(m["status"])}</span></div>')
    return (
        '<div class="tr-card"><div class="tr-card-title">Recursos agora</div><div class="tr-res">'
        f'<div><div class="tr-res-head">Leitos livres</div>{"".join(alas)}</div>'
        f'<div><div class="tr-res-head">Médicos de plantão</div>{"".join(medicos)}</div>'
        '</div></div>'
    )


def saudacao() -> str:
    return (
        f'<div class="tr-hello">Olá! Eu sou a <b>{NOME_ASSISTENTE}</b> e vou te ajudar na triagem. '
        'Me conte a <b>idade</b>, a <b>queixa</b> e os <b>sinais vitais</b> que você tiver.'
        '<ul><li>Se faltar algum dado, eu pergunto. Nunca estimo valores.</li>'
        '<li>Ações como acionar a emergência só acontecem com a sua aprovação.</li></ul></div>'
    )


def digitando() -> str:
    return f'<div class="tr-typing"><span></span><span></span><span></span>{NOME_ASSISTENTE} está analisando o caso...</div>'


def rotulo_consultas(itens: list[tuple[str, bool]]) -> str:
    """Rótulo do expander de consultas de um passo do agente. itens = [(nome, teve_erro)]."""
    nomes = ", ".join(f"{nome} (dado inválido)" if erro else nome for nome, erro in itens)
    return f"{'⚠' if any(erro for _, erro in itens) else '✓'} Consultou: {nomes}"


def legenda_classificacao() -> str:
    linhas = "".join(
        f'<div class="tr-legend-row"><span class="tr-dot" style="background:{n["cor"]}"></span>'
        f'<span><b>{nome.title()}</b> · {n["descricao"]}</span></div>'
        for nome, n in NIVEIS.items()
    )
    return f'<div class="tr-legend">{linhas}</div>'


def como_funciona() -> str:
    return (
        '<div class="tr-help"><ul>'
        '<li><b>Sinais de alarme</b> (dor torácica, AVC, sangramento...) são detectados por regra e elevam o risco para vermelho.</li>'
        '<li>O <b>NEWS2</b> usa 7 sinais vitais e vale a partir de 16 anos.</li>'
        '<li>Cada sinal vital mostra quantos pontos somou no escore.</li>'
        '</ul></div>'
    )


def aviso_legal() -> str:
    return (
        '<div class="tr-disclaimer">Ferramenta de apoio à decisão para profissionais de saúde. '
        'Não substitui a avaliação clínica. Leitos, escalas e protocolos são simulados.</div>'
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
