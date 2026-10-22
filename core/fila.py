"""
Fila de pacientes do plantão e pendências do hospital.

A fila é montada a partir das triagens salvas no checkpointer do grafo: cada thread
é um paciente, e o primeiro checkpoint marca a hora de chegada. Nada aqui chama o LLM.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from langchain_core.messages import HumanMessage

from core.hospital import ESCALA_PLANTAO, LEITOS, vagas
from utils.text import conteudo_para_texto

# Tempo-alvo para o início do atendimento médico, por classificação (minutos).
# Definido pelo hospital; os valores abaixo seguem a referência usual de Manchester.
META_MINUTOS = {"VERMELHO": 0, "AMARELO": 60, "VERDE": 120}

_ORDEM = {"VERMELHO": 0, "AMARELO": 1, "VERDE": 2}


@dataclass
class Paciente:
    thread_id: str
    chegada: datetime
    classificacao: Optional[str] = None
    idade: Optional[int] = None
    escore: Optional[int] = None
    red_flags: list[str] = field(default_factory=list)
    queixa: str = ""
    aguardando_aprovacao: bool = False
    emergencia_acionada: bool = False
    pediatrico: bool = False

    @property
    def codigo(self) -> str:
        return self.thread_id[:6].upper()

    def espera_min(self, agora: datetime) -> int:
        return max(0, int((agora - self.chegada).total_seconds() // 60))

    @property
    def status(self) -> str:
        if self.aguardando_aprovacao:
            return "Aguardando aprovação"
        if self.emergencia_acionada:
            return "Equipe acionada"
        if self.classificacao or self.pediatrico:
            return "Aguardando atendimento"
        return "Em triagem"

    def fora_da_meta(self, agora: datetime) -> bool:
        if self.classificacao == "VERMELHO":
            return not self.emergencia_acionada  # vermelho exige acionamento imediato
        meta = META_MINUTOS.get(self.classificacao)
        return meta is not None and self.espera_min(agora) > meta


def _chave_ordem(p: Paciente):
    # Mais grave primeiro; dentro da mesma cor, quem chegou antes. Triagens em andamento por último.
    return (_ORDEM.get(p.classificacao, 3), p.chegada)


def listar_pacientes(grafo) -> list[Paciente]:
    """Pacientes ainda na fila (não marcados como atendidos), do mais grave ao menos grave."""
    chegadas: dict[str, datetime] = {}
    for registro in grafo.checkpointer.list(None):
        thread_id = registro.config["configurable"]["thread_id"]
        ts = datetime.fromisoformat(registro.checkpoint["ts"])
        chegadas[thread_id] = min(chegadas.get(thread_id, ts), ts)

    pacientes = []
    for thread_id, chegada in chegadas.items():
        snapshot = grafo.get_state({"configurable": {"thread_id": thread_id}})
        estado = snapshot.values or {}
        mensagens = estado.get("messages") or []
        if not mensagens or estado.get("atendido"):
            continue

        primeira = next((m for m in mensagens if isinstance(m, HumanMessage)), None)
        queixa = conteudo_para_texto(primeira.content) if primeira else ""
        pacientes.append(Paciente(
            thread_id=thread_id,
            chegada=chegada,
            classificacao=estado.get("classificacao"),
            idade=estado.get("idade"),
            escore=estado.get("escore_news2"),
            red_flags=estado.get("red_flags") or [],
            queixa=queixa if len(queixa) <= 110 else queixa[:107].rstrip() + "...",
            aguardando_aprovacao=any(t.interrupts for t in snapshot.tasks),
            emergencia_acionada=bool(estado.get("emergencia_acionada")),
            pediatrico=bool(estado.get("escore_nao_aplicavel")),
        ))
    return sorted(pacientes, key=_chave_ordem)


def marcar_atendido(grafo, thread_id: str) -> None:
    """Tira o paciente da fila. Registrado 'como se' fosse o agente, para a thread terminar em END."""
    grafo.update_state({"configurable": {"thread_id": thread_id}}, {"atendido": True}, as_node="agent")


def pendencias(pacientes: list[Paciente], agora: Optional[datetime] = None) -> list[tuple[str, str]]:
    """
    O que precisa de atenção agora, do mais urgente ao menos urgente.
    Cada item é (nivel, texto), com nivel em: "critico", "alerta", "info".
    """
    agora = agora or datetime.now(timezone.utc)
    itens = []

    for p in pacientes:
        if p.aguardando_aprovacao:
            itens.append(("critico", f"Paciente #{p.codigo} aguarda sua autorização para acionar a emergência"))
    for p in pacientes:
        if p.classificacao == "VERMELHO" and not p.emergencia_acionada and not p.aguardando_aprovacao:
            itens.append(("critico", f"Paciente #{p.codigo} é VERMELHO e a equipe ainda não foi acionada"))
    for p in pacientes:
        if p.classificacao in ("AMARELO", "VERDE") and p.fora_da_meta(agora):
            itens.append(("alerta", f"Paciente #{p.codigo} ({p.classificacao.lower()}) espera há {p.espera_min(agora)} min, "
                                    f"acima da meta de {META_MINUTOS[p.classificacao]} min"))

    for ala in LEITOS:
        if vagas(ala) == 0:
            itens.append(("alerta", f"{ala} sem leitos livres: avaliar protocolo de superlotação"))

    for especialidade, medico in ESCALA_PLANTAO.items():
        if medico["status"] != "Disponível":
            itens.append(("info", f"{especialidade}: {medico['nome']} está {medico['status'].lower()} (ramal {medico['ramal']})"))

    em_triagem = sum(1 for p in pacientes if p.status == "Em triagem")
    if em_triagem:
        itens.append(("info", f"{em_triagem} triagem(ns) em andamento, ainda sem classificação"))
    return itens
