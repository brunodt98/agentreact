"""
Blocos visuais do painel do plantão (indicadores, fila, leitos, equipe e pendências).
Cada função devolve HTML para st.html; textos variáveis passam por html.escape.
"""
from datetime import datetime
from html import escape

from core.fila import META_MINUTOS, Paciente
from ui.componentes import NIVEIS

# Atenção: não use o caractere "menor que" dentro do CSS (nem em comentários): o st.html descarta o bloco.
CSS = """
<style>
.tp-section { display: flex; align-items: center; justify-content: space-between; margin: 4px 0 10px; }
.tp-title { font-size: .78rem; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: .08em; }
.tp-count { font-size: .75rem; font-weight: 600; color: #334155; background: #E2E8F0; border-radius: 999px; padding: 2px 9px; }

.tp-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
@media (max-width: 900px) { .tp-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.tp-kpi { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px; padding: 14px 16px; }
.tp-kpi-label { font-size: .8rem; font-weight: 600; color: #64748B; }
.tp-kpi-value { font-size: 2rem; font-weight: 700; color: #0F172A; line-height: 1.15; margin-top: 2px; }
.tp-kpi-value small { font-size: .95rem; font-weight: 500; color: #64748B; margin-left: 4px; }
.tp-kpi-sub { font-size: .78rem; color: #64748B; margin-top: 4px; display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.tp-dot { width: 9px; height: 9px; border-radius: 3px; display: inline-block; }
.tp-mini { display: inline-flex; align-items: center; gap: 4px; font-weight: 600; color: #334155; }

/* Linha da fila: a borda esquerda leva a cor da classificação */
[class*="st-key-fila_"] { background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 5px solid #CBD5E1;
  border-radius: 12px; padding: 10px 14px; gap: 6px !important; }
[class*="st-key-fila_VERMELHO"] { border-left-color: #DC2626; }
[class*="st-key-fila_AMARELO"] { border-left-color: #D97706; }
[class*="st-key-fila_VERDE"] { border-left-color: #16A34A; }
[class*="st-key-fila_PEDIATRICO"] { border-left-color: #2563EB; }
[class*="st-key-fila_"] button { min-height: 32px; padding: 2px 10px; font-size: .82rem; }
.tp-row-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tp-level { font-size: .72rem; font-weight: 700; border-radius: 6px; padding: 2px 8px; letter-spacing: .03em; }
.tp-code { font-weight: 700; color: #0F172A; }
.tp-meta { font-size: .8rem; color: #64748B; }
.tp-queixa { font-size: .86rem; color: #334155; margin-top: 3px; }
.tp-wait { margin-left: auto; font-size: .8rem; font-weight: 600; color: #334155; white-space: nowrap; }
.tp-wait.late { color: #B91C1C; }
.tp-status { font-size: .72rem; font-weight: 600; border-radius: 999px; padding: 2px 9px; border: 1px solid #E2E8F0; color: #475569; }
.tp-status.alerta { color: #991B1B; background: #FEF2F2; border-color: #FECACA; }
.tp-status.ok { color: #0F766E; background: #F0FDFA; border-color: #99F6E4; }
.tp-flag { font-size: .72rem; font-weight: 600; color: #B91C1C; background: #FEE2E2; border-radius: 999px; padding: 2px 8px; }

.tp-empty { background: #FFFFFF; border: 1px dashed #CBD5E1; border-radius: 14px; padding: 26px; text-align: center; color: #64748B; }
.tp-empty b { display: block; color: #0F172A; font-size: 1rem; margin-bottom: 4px; }

.tp-card { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px; padding: 12px 14px; }
.tp-pend { display: flex; gap: 10px; align-items: flex-start; padding: 8px 0; font-size: .86rem; color: #334155; border-bottom: 1px solid #F1F5F9; }
.tp-pend:last-child { border-bottom: 0; }
.tp-icon { width: 20px; height: 20px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center; justify-content: center;
  font-size: .72rem; font-weight: 800; color: #FFFFFF; margin-top: 1px; }
.tp-ok { font-size: .86rem; color: #0F766E; }

.tp-meter-row { padding: 7px 0; }
.tp-meter-head { display: flex; justify-content: space-between; font-size: .85rem; color: #334155; margin-bottom: 5px; gap: 8px; }
.tp-meter-head b { color: #0F172A; }
.tp-meter { height: 8px; border-radius: 4px; overflow: hidden; }
.tp-meter-fill { height: 100%; border-radius: 4px; }
.tp-tag { font-size: .7rem; font-weight: 700; border-radius: 6px; padding: 1px 6px; margin-left: 6px; }

.tp-team { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #F1F5F9; }
.tp-team:last-child { border-bottom: 0; }
.tp-avatar { width: 34px; height: 34px; border-radius: 50%; background: #ECFEFF; color: #0E7490; font-weight: 700; font-size: .8rem;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.tp-team-name { font-size: .88rem; font-weight: 600; color: #0F172A; line-height: 1.2; }
.tp-team-sub { font-size: .76rem; color: #64748B; }
.tp-team-status { margin-left: auto; font-size: .74rem; font-weight: 600; display: flex; align-items: center; gap: 6px; white-space: nowrap; }
</style>
"""

_PENDENCIA = {
    "critico": ("!", "#DC2626"),
    "alerta": ("!", "#D97706"),
    "info": ("i", "#2563EB"),
}

_STATUS_MEDICO = {
    "Disponível": "#16A34A",
    "Em atendimento": "#D97706",
    "Em cirurgia": "#DC2626",
}


def secao(titulo: str, contagem=None) -> str:
    badge = f'<span class="tp-count">{contagem}</span>' if contagem is not None else ""
    return f'<div class="tp-section"><span class="tp-title">{escape(titulo)}</span>{badge}</div>'


def _kpi(rotulo: str, valor: str, sufixo: str = "", sub: str = "") -> str:
    sufixo_html = f"<small>{escape(sufixo)}</small>" if sufixo else ""
    return (f'<div class="tp-kpi"><div class="tp-kpi-label">{escape(rotulo)}</div>'
            f'<div class="tp-kpi-value">{valor}{sufixo_html}</div><div class="tp-kpi-sub">{sub}</div></div>')


def indicadores(pacientes: list[Paciente], leitos: dict, escala: dict, agora: datetime) -> str:
    """Quatro números que resumem o plantão."""
    por_cor = {cor: sum(1 for p in pacientes if p.classificacao == cor) for cor in NIVEIS}
    # Pediátricos (sem NEWS2) e triagens em andamento também entram na legenda, para a soma bater
    grupos = [(f"{n} {cor.lower()}", NIVEIS[cor]["cor"]) for cor, n in por_cor.items() if n]
    pediatricos = sum(1 for p in pacientes if p.classificacao is None and p.pediatrico)
    em_triagem = sum(1 for p in pacientes if p.status == "Em triagem")
    if pediatricos:
        grupos.append((f"{pediatricos} pediátrico{'s' if pediatricos > 1 else ''}", "#2563EB"))
    if em_triagem:
        grupos.append((f"{em_triagem} em triagem", "#94A3B8"))
    composicao = "".join(
        f'<span class="tp-mini"><span class="tp-dot" style="background:{cor}"></span>{escape(texto)}</span>'
        for texto, cor in grupos
    ) or "Nenhum paciente aguardando"

    if pacientes:
        mais_antigo = max(pacientes, key=lambda p: p.espera_min(agora))
        espera = str(mais_antigo.espera_min(agora))
        sub_espera = f"Paciente #{escape(mais_antigo.codigo)}" + (" · acima da meta" if mais_antigo.fora_da_meta(agora) else "")
    else:
        espera, sub_espera = "0", "Sem espera no momento"

    livres = sum(l["total"] - l["ocupados"] for l in leitos.values())
    total = sum(l["total"] for l in leitos.values())
    lotadas = [ala for ala, l in leitos.items() if l["total"] == l["ocupados"]]
    sub_leitos = ("Sem vaga: " + ", ".join(lotadas)) if lotadas else "Todas as alas com vaga"

    disponiveis = sum(1 for m in escala.values() if m["status"] == "Disponível")
    indisponiveis = [esp for esp, m in escala.items() if m["status"] != "Disponível"]
    sub_medicos = ("Ocupados: " + ", ".join(indisponiveis)) if indisponiveis else "Equipe completa disponível"

    return (
        '<div class="tp-kpis">'
        + _kpi("Pacientes na fila", str(len(pacientes)), sub=composicao)
        + _kpi("Maior espera", espera, "min", sub_espera)
        + _kpi("Leitos livres", str(livres), f"de {total}", escape(sub_leitos))
        + _kpi("Médicos disponíveis", str(disponiveis), f"de {len(escala)}", escape(sub_medicos))
        + "</div>"
    )


def linha_fila(p: Paciente, agora: datetime) -> str:
    """Conteúdo de uma linha da fila (os botões ficam ao lado, em Streamlit)."""
    if p.classificacao in NIVEIS:
        n = NIVEIS[p.classificacao]
        nivel = f'<span class="tp-level" style="color:{n["cor"]};background:{n["fundo"]}">{p.classificacao}</span>'
    elif p.pediatrico:
        nivel = '<span class="tp-level" style="color:#2563EB;background:#EFF6FF">PEDIÁTRICO</span>'
    else:
        nivel = '<span class="tp-level" style="color:#475569;background:#F1F5F9">EM TRIAGEM</span>'

    detalhes = []
    if p.idade is not None:
        detalhes.append(f"{p.idade} anos")
    if p.escore is not None:
        detalhes.append(f"NEWS2 {p.escore}")
    detalhes.append(f"chegou {p.chegada.astimezone().strftime('%H:%M')}")

    status_cls = "alerta" if p.aguardando_aprovacao else ("ok" if p.emergencia_acionada else "")
    flags = "".join(f'<span class="tp-flag">{escape(f)}</span>' for f in p.red_flags)

    espera = p.espera_min(agora)
    atrasado = p.fora_da_meta(agora)
    meta = META_MINUTOS.get(p.classificacao)
    dica = f"Meta: {meta} min" if meta is not None else "Sem meta: triagem em andamento"
    return (
        f'<div class="tp-row-top">{nivel}<span class="tp-code">#{escape(p.codigo)}</span>'
        f'<span class="tp-meta">{" · ".join(detalhes)}</span>'
        f'<span class="tp-status {status_cls}">{escape(p.status)}</span>{flags}'
        f'<span class="tp-wait{" late" if atrasado else ""}" title="{dica}">{"⚠ " if atrasado else ""}espera {espera} min</span></div>'
        f'<div class="tp-queixa">{escape(p.queixa)}</div>'
    )


def fila_vazia() -> str:
    return ('<div class="tp-empty"><b>Nenhum paciente na fila</b>'
            'As triagens feitas na aba Triagem aparecem aqui, da mais grave para a menos grave.</div>')


def lista_pendencias(itens: list[tuple[str, str]]) -> str:
    if not itens:
        return '<div class="tp-card"><div class="tp-ok">✓ Nenhuma pendência no momento</div></div>'
    linhas = "".join(
        f'<div class="tp-pend"><span class="tp-icon" style="background:{_PENDENCIA[nivel][1]}">{_PENDENCIA[nivel][0]}</span>'
        f'<span>{escape(texto)}</span></div>'
        for nivel, texto in itens
    )
    return f'<div class="tp-card">{linhas}</div>'


def _cores_ocupacao(ocupacao: float) -> tuple[str, str, str]:
    """(preenchimento, trilho, rótulo): o trilho é um tom claro da mesma cor do preenchimento."""
    if ocupacao >= 1:
        return "#DC2626", "#FEE2E2", "Lotada"
    if ocupacao >= 0.8:
        return "#D97706", "#FEF3C7", "Quase cheia"
    return "#0E7490", "#CFFAFE", ""


def ocupacao_leitos(leitos: dict) -> str:
    linhas = []
    for ala, l in leitos.items():
        livres = l["total"] - l["ocupados"]
        ocupacao = l["ocupados"] / l["total"]
        cor, trilho, rotulo = _cores_ocupacao(ocupacao)
        tag = f'<span class="tp-tag" style="color:{cor};background:{trilho}">{rotulo}</span>' if rotulo else ""
        linhas.append(
            f'<div class="tp-meter-row"><div class="tp-meter-head"><span>{escape(ala)}{tag}</span>'
            f'<span><b>{livres}</b> livre{"s" if livres != 1 else ""} de {l["total"]}</span></div>'
            f'<div class="tp-meter" style="background:{trilho}" title="{escape(ala)}: {l["ocupados"]} de {l["total"]} ocupados ({ocupacao:.0%})">'
            f'<div class="tp-meter-fill" style="width:{ocupacao:.0%};background:{cor}"></div></div></div>'
        )
    return f'<div class="tp-card">{"".join(linhas)}</div>'


def _iniciais(nome: str) -> str:
    partes = [p for p in nome.replace("Dra.", "").replace("Dr.", "").split() if p]
    return "".join(p[0] for p in partes[:2]).upper()


def equipe(escala: dict, turno: str) -> str:
    linhas = []
    for especialidade, m in escala.items():
        cor = _STATUS_MEDICO.get(m["status"], "#64748B")
        linhas.append(
            f'<div class="tp-team"><div class="tp-avatar">{escape(_iniciais(m["nome"]))}</div>'
            f'<div><div class="tp-team-name">{escape(m["nome"])}</div>'
            f'<div class="tp-team-sub">{escape(especialidade)} · ramal {escape(m["ramal"])}</div></div>'
            f'<div class="tp-team-status" style="color:{cor}"><span class="tp-dot" style="background:{cor}"></span>{escape(m["status"])}</div></div>'
        )
    return f'<div class="tp-card"><div class="tp-meta">Turno {escape(turno)}</div>{"".join(linhas)}</div>'
