"""
Blocos visuais do painel do plantão (indicadores, fila, pendências e mapa do hospital).
Cada função devolve HTML para st.html; textos variáveis passam por html.escape.
Os cartões (.tr-card) e as cores básicas vêm do CSS global em ui.componentes.
"""
from datetime import datetime
from html import escape

from core.fila import META_MINUTOS, Paciente
from core.hospital import ENFERMAGEM, LEITOS_DETALHE, medico_no_leito, medicos_em
from ui.componentes import NIVEIS

# Atenção: não use o caractere "menor que" dentro do CSS (nem em comentários): o st.html descarta o bloco.
CSS = """
<style>
.tp-section { display: flex; align-items: baseline; justify-content: space-between; margin: 6px 2px 10px; }
.tp-title { font-size: 1rem; font-weight: 600; color: #0F172A; }
.tp-count { font-size: .82rem; color: #64748B; }

/* Indicadores do topo */
.tp-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 6px; }
@media (max-width: 900px) { .tp-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.tp-kpi { background: #FFFFFF; border: 1px solid #E8EDF3; border-radius: 16px; padding: 12px 16px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, .04), 0 4px 16px rgba(15, 23, 42, .04); }
.tp-kpi-label { font-size: .82rem; color: #64748B; }
.tp-kpi-value { font-size: 1.5rem; font-weight: 700; color: #0F172A; line-height: 1.2; margin-top: 2px;
  font-variant-numeric: tabular-nums; }
.tp-kpi-value small { font-size: .9rem; font-weight: 500; color: #94A3B8; margin-left: 4px; }
.tp-kpi-value.alerta { color: #B91C1C; }
.tp-kpi-sub { font-size: .78rem; color: #64748B; margin-top: 2px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.tp-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.tp-mini { display: inline-flex; align-items: center; gap: 5px; }

/* Linha da fila: a borda esquerda leva a cor da classificação */
[class*="st-key-fila_"] { background: #FFFFFF; border: 1px solid #E8EDF3; border-left: 4px solid #CBD5E1;
  border-radius: 14px; padding: 12px 14px 12px 16px; box-shadow: 0 1px 2px rgba(15, 23, 42, .04); }
[class*="st-key-fila_VERMELHO"] { border-left-color: #DC2626; }
[class*="st-key-fila_AMARELO"] { border-left-color: #D97706; }
[class*="st-key-fila_VERDE"] { border-left-color: #16A34A; }
[class*="st-key-fila_PEDIATRICO"] { border-left-color: #2563EB; }
[class*="st-key-fila_"] button { min-height: 34px; font-size: .85rem; }
.tp-row-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tp-row-meta { font-size: .8rem; color: #64748B; margin-top: 4px; font-variant-numeric: tabular-nums; }
.tp-level { font-size: .74rem; font-weight: 700; border-radius: 999px; padding: 2px 10px; }
.tp-code { font-weight: 600; color: #0F172A; }
.tp-wait b { color: #0F172A; font-weight: 600; }
.tp-wait.late, .tp-wait.late b { color: #B91C1C; }
.tp-queixa { font-size: .88rem; color: #334155; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tp-status { font-size: .72rem; font-weight: 600; border-radius: 999px; padding: 2px 9px; }
.tp-status.alerta { color: #92400E; background: #FEF3C7; }
.tp-status.ok { color: #0F766E; background: #CCFBF1; }
.tp-flag { font-size: .72rem; font-weight: 600; color: #B91C1C; background: #FEE2E2; border-radius: 999px; padding: 2px 9px; }

.tp-empty { background: #FFFFFF; border: 1px dashed #CBD5E1; border-radius: 16px; padding: 32px 24px; text-align: center;
  color: #64748B; font-size: .9rem; }
.tp-empty b { display: block; color: #0F172A; font-size: 1rem; margin-bottom: 4px; }

/* Pendências */
.tp-pend { display: flex; gap: 10px; align-items: flex-start; padding: 8px 0; font-size: .86rem; color: #334155;
  border-bottom: 1px solid #F1F4F8; }
.tp-pend:last-child { border-bottom: 0; padding-bottom: 0; }
.tp-pend .tp-dot { margin-top: 6px; }
.tp-ok { font-size: .88rem; color: #0F766E; }

/* Leitos */
.tp-meter-row { padding: 6px 0; }
.tp-meter-head { display: flex; justify-content: space-between; font-size: .86rem; color: #334155; margin-bottom: 5px; gap: 8px; }
.tp-meter-head b { color: #0F172A; }
.tp-meter { height: 6px; border-radius: 3px; overflow: hidden; }
.tp-meter-fill { height: 100%; border-radius: 3px; }
.tp-tag { font-size: .7rem; font-weight: 600; border-radius: 999px; padding: 1px 7px; margin-left: 6px; }

/* --- Mapa do hospital: planta com as alas lado a lado --- */
.tm-card { padding: 16px 18px 12px; }
.tm-card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.tm-card-head .tr-card-title { margin: 0; font-size: 1rem; }
.tm-legend { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: .76rem; color: #64748B; }
.tm-key { display: inline-flex; align-items: center; gap: 5px; }
.tm-sw { width: 16px; height: 13px; border-radius: 4px; display: inline-flex; align-items: center; justify-content: center; }
.tm-sw span { width: 5px; height: 5px; border-radius: 50%; }
.tm-sw.livre { border: 1.5px dashed #86EFAC; background: #FFFFFF; }
.tm-sep { width: 1px; height: 14px; background: #E2E8F0; }
.tm-plan { display: grid; gap: 12px; grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-template-areas: "espera emerg uti" "adulto adulto ped" "cc cc cc"; }
@media (max-width: 1100px) { .tm-plan { grid-template-columns: minmax(0, 1fr);
  grid-template-areas: "espera" "emerg" "uti" "adulto" "ped" "cc"; } }
.tm-room { background: #F8FAFC; border: 1px solid #E8EDF3; border-radius: 14px; padding: 12px; display: flex;
  flex-direction: column; gap: 8px; min-width: 0; }
.tm-room-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.tm-room-name { font-weight: 600; font-size: .9rem; color: #0F172A; white-space: nowrap; }
.tm-room-free { font-size: .8rem; color: #64748B; white-space: nowrap; }
.tm-room-free b { color: #0F172A; }
.tm-beds { display: grid; grid-template-columns: repeat(auto-fill, minmax(44px, 1fr)); gap: 6px; }
.tm-bed { position: relative; height: 40px; border-radius: 8px; border: 1.5px solid transparent; cursor: default;
  display: flex; align-items: flex-start; justify-content: space-between; padding: 3px 5px; }
.tm-bed:hover { outline: 2px solid #0F172A; outline-offset: 1px; z-index: 5; }
.tm-bed.livre { background: #FFFFFF; border: 1.5px dashed #86EFAC; flex-direction: column; justify-content: space-between; }
.tm-num { font-size: .68rem; font-weight: 600; color: #475569; font-variant-numeric: tabular-nums; }
.tm-lbl { font-size: .62rem; color: #16A34A; font-weight: 600; }
.tm-pulse { width: 8px; height: 8px; border-radius: 50%; margin-top: 2px; }
.tm-doc-mark { position: absolute; right: -5px; bottom: -5px; width: 20px; height: 20px; border-radius: 50%; color: #FFFFFF;
  font-size: .56rem; font-weight: 700; display: flex; align-items: center; justify-content: center; border: 2px solid #FFFFFF; }
.tm-tip { display: none; position: absolute; left: 50%; bottom: calc(100% + 8px); transform: translateX(-50%); width: 230px;
  background: #0F172A; color: #E2E8F0; border-radius: 10px; padding: 10px 12px; font-size: .76rem; line-height: 1.45;
  z-index: 50; box-shadow: 0 8px 24px rgba(15, 23, 42, .25); text-align: left; pointer-events: none; }
.tm-tip b { color: #FFFFFF; display: block; margin-bottom: 2px; }
.tm-bed:hover .tm-tip, .tm-wait:hover .tm-tip { display: block; }
.tm-staff { display: flex; flex-wrap: wrap; gap: 6px 14px; }
.tm-staff:empty { display: none; }
.tm-doc { display: flex; align-items: center; gap: 8px; min-width: 0; }
.tm-av { width: 28px; height: 28px; border-radius: 50%; background: #ECFEFF; color: #0E7490; font-size: .66rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin: 3px; }
.tm-doc b { display: block; font-size: .8rem; color: #0F172A; font-weight: 600; line-height: 1.2; white-space: nowrap; }
.tm-doc small { display: flex; align-items: center; gap: 5px; font-size: .72rem; color: #64748B; white-space: nowrap; }
.tm-nurses { font-size: .72rem; color: #94A3B8; margin-top: auto; }
.tm-waits { display: flex; flex-wrap: wrap; gap: 6px; align-content: flex-start; }
.tm-wait { position: relative; display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 4px 10px;
  font-size: .78rem; color: #334155; }
.tm-wait b { color: #0F172A; font-weight: 600; }
.tm-wait .late { color: #B91C1C; font-weight: 600; }
.tm-empty { font-size: .8rem; color: #94A3B8; }
.tm-cc { flex-direction: row; align-items: center; gap: 20px; padding: 10px 12px; }
.tm-hint { font-size: .74rem; color: #94A3B8; margin-top: 10px; }
</style>
"""

_PENDENCIA = {"critico": "#DC2626", "alerta": "#D97706", "info": "#2563EB"}

_STATUS_MEDICO = {
    "Disponível": "#16A34A",
    "Em atendimento": "#D97706",
    "Em cirurgia": "#DC2626",
}


def secao(titulo: str, detalhe: str = "") -> str:
    detalhe_html = f'<span class="tp-count">{escape(detalhe)}</span>' if detalhe else ""
    return f'<div class="tp-section"><span class="tp-title">{escape(titulo)}</span>{detalhe_html}</div>'


def _cartao(titulo: str, conteudo: str, detalhe: str = "") -> str:
    detalhe_html = f'<span class="tr-count">{escape(detalhe)}</span>' if detalhe else ""
    return f'<div class="tr-card"><div class="tr-card-title">{escape(titulo)}{detalhe_html}</div>{conteudo}</div>'


def _kpi(rotulo: str, valor: str, sufixo: str = "", sub: str = "", alerta: bool = False) -> str:
    sufixo_html = f"<small>{escape(sufixo)}</small>" if sufixo else ""
    return (f'<div class="tp-kpi"><div class="tp-kpi-label">{escape(rotulo)}</div>'
            f'<div class="tp-kpi-value{" alerta" if alerta else ""}">{valor}{sufixo_html}</div>'
            f'<div class="tp-kpi-sub">{sub}</div></div>')


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

    atrasado = False
    if pacientes:
        mais_antigo = max(pacientes, key=lambda p: p.espera_min(agora))
        espera = str(mais_antigo.espera_min(agora))
        atrasado = mais_antigo.fora_da_meta(agora)
        sub_espera = f"Paciente #{escape(mais_antigo.codigo)}" + (" · acima da meta" if atrasado else "")
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
        + _kpi("Maior espera", espera, "min", sub_espera, alerta=atrasado)
        + _kpi("Leitos livres", str(livres), f"de {total}", escape(sub_leitos))
        + _kpi("Médicos disponíveis", str(disponiveis), f"de {len(escala)}", escape(sub_medicos))
        + "</div>"
    )


def linha_fila(p: Paciente, agora: datetime) -> str:
    """Conteúdo de uma linha da fila (os botões ficam ao lado, em Streamlit)."""
    if p.classificacao in NIVEIS:
        n = NIVEIS[p.classificacao]
        nivel = f'<span class="tp-level" style="color:{n["cor"]};background:{n["fundo"]}">{p.classificacao.title()}</span>'
    elif p.pediatrico:
        nivel = '<span class="tp-level" style="color:#2563EB;background:#EFF6FF">Pediátrico</span>'
    else:
        nivel = '<span class="tp-level" style="color:#475569;background:#F1F5F9">Em triagem</span>'

    detalhes = []
    if p.idade is not None:
        detalhes.append(f"{p.idade} anos")
    if p.escore is not None:
        detalhes.append(f"NEWS2 {p.escore}")
    detalhes.append(f"chegou {p.chegada.astimezone().strftime('%H:%M')}")

    # O status só aparece quando pede atenção ou traz novidade; o resto é "aguardando"
    tags = []
    if p.aguardando_aprovacao or p.emergencia_acionada:
        tags.append(f'<span class="tp-status {"alerta" if p.aguardando_aprovacao else "ok"}">{escape(p.status)}</span>')
    tags += [f'<span class="tp-flag">{escape(f)}</span>' for f in p.red_flags]

    espera = p.espera_min(agora)
    atrasado = p.fora_da_meta(agora)
    meta = META_MINUTOS.get(p.classificacao)
    dica = f"Meta: {meta} min" if meta is not None else "Sem meta: triagem em andamento"
    detalhes.append(f'<span class="tp-wait{" late" if atrasado else ""}" title="{dica}">'
                    f'{"⚠ " if atrasado else ""}espera <b>{espera} min</b></span>')
    queixa = f'<div class="tp-queixa" title="{escape(p.queixa)}">{escape(p.queixa)}</div>' if p.queixa else ""
    return (
        f'<div class="tp-row-top">{nivel}<span class="tp-code">#{escape(p.codigo)}</span>{"".join(tags)}</div>'
        f'{queixa}<div class="tp-row-meta">{" · ".join(detalhes)}</div>'
    )


def fila_vazia() -> str:
    return ('<div class="tp-empty"><b>Nenhum paciente na fila</b>'
            'As triagens aparecem aqui, da mais grave para a menos grave.</div>')


def lista_pendencias(itens: list[tuple[str, str]]) -> str:
    if not itens:
        return _cartao("Pendências", '<div class="tp-ok">✓ Nenhuma pendência no momento</div>')
    linhas = "".join(
        f'<div class="tp-pend"><span class="tp-dot" style="background:{_PENDENCIA[nivel]}"></span>'
        f'<span>{escape(texto)}</span></div>'
        for nivel, texto in itens
    )
    return _cartao("Pendências", linhas, str(len(itens)))


# Gravidade dos internados -> (rótulo, cor forte, fundo)
GRAVIDADE = {
    "critico": ("Crítico", "#DC2626", "#FEE2E2"),
    "atencao": ("Atenção", "#D97706", "#FEF3C7"),
    "estavel": ("Estável", "#0E7490", "#E0F2F7"),
}

# Posição de cada bloco na planta (grid-area do CSS)
_AREA = {
    "Emergência": "emerg",
    "UTI": "uti",
    "Enfermaria Adulto": "adulto",
    "Enfermaria Pediátrica": "ped",
}


def _cores_ocupacao(ocupacao: float) -> tuple[str, str, str]:
    """(preenchimento, trilho, rótulo): o trilho é um tom claro da mesma cor do preenchimento."""
    if ocupacao >= 1:
        return "#DC2626", "#FEE2E2", "Lotada"
    if ocupacao >= 0.8:
        return "#D97706", "#FEF3C7", "Quase cheia"
    return "#0E7490", "#E0F2F7", ""


def _iniciais(nome: str) -> str:
    partes = [p for p in nome.replace("Dra.", "").replace("Dr.", "").replace("Enf.", "").split() if p]
    return "".join(p[0] for p in partes[:2]).upper()


def _medico(especialidade: str, m: dict) -> str:
    cor = _STATUS_MEDICO.get(m["status"], "#64748B")
    onde = f' · leito {escape(m["leito"])}' if m.get("leito") else ""
    return (
        f'<div class="tm-doc" title="{escape(m["nome"])} · {escape(especialidade)} · ramal {escape(m["ramal"])}">'
        f'<span class="tm-av" style="box-shadow:0 0 0 2px #FFFFFF,0 0 0 4px {cor}">{escape(_iniciais(m["nome"]))}</span>'
        f'<span><b>{escape(m["nome"])}</b><small><span class="tp-dot" style="background:{cor}"></span>'
        f'{escape(m["status"])}{onde}</small></span></div>'
    )


def _leito(leito: dict) -> str:
    codigo = leito["codigo"]
    numero = codigo.split("-")[-1]
    p = leito["paciente"]
    if p is None:
        return (f'<div class="tm-bed livre"><span class="tm-num">{numero}</span><span class="tm-lbl">livre</span>'
                f'<div class="tm-tip"><b>Leito {escape(codigo)}</b>Livre para internação</div></div>')

    rotulo, cor, fundo = GRAVIDADE[p["gravidade"]]
    medico = medico_no_leito(codigo)
    marca = (f'<span class="tm-doc-mark" style="background:{_STATUS_MEDICO[medico["status"]]}">'
             f'{escape(_iniciais(medico["nome"]))}</span>') if medico else ""
    dias = "Chegou hoje" if p["dias"] == 0 else f'Internado há {p["dias"]} dia{"s" if p["dias"] > 1 else ""}'
    linha_medico = f'<div>Em atendimento: {escape(medico["nome"])}</div>' if medico else ""
    return (
        f'<div class="tm-bed" style="background:{fundo};border-color:{fundo}">'
        f'<span class="tm-num">{numero}</span><span class="tm-pulse" style="background:{cor}"></span>{marca}'
        f'<div class="tm-tip"><b>Leito {escape(codigo)} · {escape(p["nome"])}, {p["idade"]} anos</b>'
        f'<div>{escape(p["motivo"])}</div>'
        f'<div><span class="tp-dot" style="background:{cor}"></span> {rotulo} · {dias}</div>{linha_medico}</div></div>'
    )


def _ala(ala: str, leitos: list[dict]) -> str:
    total = len(leitos)
    livres = sum(1 for l in leitos if l["paciente"] is None)
    ocupacao = (total - livres) / total
    cor, trilho, rotulo = _cores_ocupacao(ocupacao)
    tag = f'<span class="tp-tag" style="color:{cor};background:{trilho}">{rotulo}</span>' if rotulo else ""
    medicos = "".join(_medico(esp, m) for esp, m in medicos_em(ala))
    enfermagem = ", ".join(ENFERMAGEM.get(ala, []))
    return (
        f'<div class="tm-room" style="grid-area:{_AREA[ala]}">'
        f'<div class="tm-room-head"><span class="tm-room-name">{escape(ala)}{tag}</span>'
        f'<span class="tm-room-free"><b>{livres}</b> livre{"s" if livres != 1 else ""} de {total}</span></div>'
        f'<div class="tp-meter" style="background:{trilho}"><div class="tp-meter-fill" style="width:{ocupacao:.0%};background:{cor}"></div></div>'
        f'<div class="tm-beds">{"".join(_leito(l) for l in leitos)}</div>'
        f'<div class="tm-staff">{medicos}</div>'
        + (f'<div class="tm-nurses">Enfermagem: {escape(enfermagem)}</div>' if enfermagem else "")
        + '</div>'
    )


def _sala_espera(pacientes: list[Paciente], agora: datetime) -> str:
    """Pacientes da triagem que ainda não foram atendidos, como fichas na sala de espera."""
    fichas = []
    for p in pacientes:
        if p.classificacao in NIVEIS:
            cor, fundo = NIVEIS[p.classificacao]["cor"], NIVEIS[p.classificacao]["fundo"]
        elif p.pediatrico:
            cor, fundo = "#2563EB", "#EFF6FF"
        else:
            cor, fundo = "#94A3B8", "#F1F5F9"
        atrasado = p.fora_da_meta(agora)
        fichas.append(
            f'<div class="tm-wait" style="background:{fundo}"><span class="tp-dot" style="background:{cor}"></span>'
            f'<b>#{escape(p.codigo)}</b><span class="{"late" if atrasado else ""}">{p.espera_min(agora)} min</span>'
            f'<div class="tm-tip"><b>#{escape(p.codigo)} · {escape(p.status)}</b><div>{escape(p.queixa)}</div></div></div>'
        )
    conteudo = "".join(fichas) or '<div class="tm-empty">Ninguém aguardando</div>'
    return (
        '<div class="tm-room" style="grid-area:espera">'
        '<div class="tm-room-head"><span class="tm-room-name">Sala de espera</span>'
        f'<span class="tm-room-free"><b>{len(pacientes)}</b> da triagem</span></div>'
        f'<div class="tm-waits">{conteudo}</div>'
        '<div class="tm-nurses">Passe o mouse sobre um paciente para ver a queixa</div></div>'
    )


def _centro_cirurgico() -> str:
    medicos = "".join(_medico(esp, m) for esp, m in medicos_em("Centro Cirúrgico"))
    return (
        '<div class="tm-room tm-cc" style="grid-area:cc">'
        '<span class="tm-room-name">Centro cirúrgico</span>'
        f'<div class="tm-staff">{medicos or "<span class=tm-empty>Sem cirurgias agora</span>"}</div></div>'
    )


def _legenda() -> str:
    leitos = "".join(
        f'<span class="tm-key"><span class="tm-sw" style="background:{fundo}"><span style="background:{cor}"></span></span>{r}</span>'
        for r, cor, fundo in GRAVIDADE.values()
    )
    medicos = "".join(f'<span class="tm-key"><span class="tp-dot" style="background:{c}"></span>{escape(s)}</span>'
                      for s, c in _STATUS_MEDICO.items())
    return (f'<div class="tm-legend"><span class="tm-key"><span class="tm-sw livre"></span>Livre</span>{leitos}'
            f'<span class="tm-sep"></span>{medicos}</div>')


def mapa_hospital(pacientes: list[Paciente], agora: datetime) -> str:
    """Planta do hospital: alas com cada leito, quem está internado e onde está cada médico."""
    alas = "".join(_ala(ala, leitos) for ala, leitos in LEITOS_DETALHE.items())
    return (
        '<div class="tr-card tm-card"><div class="tm-card-head"><span class="tr-card-title">Mapa do hospital</span>'
        f'{_legenda()}</div>'
        f'<div class="tm-plan">{_sala_espera(pacientes, agora)}{alas}{_centro_cirurgico()}</div>'
        '<div class="tm-hint">Passe o mouse sobre um leito para ver o paciente.</div></div>'
    )
