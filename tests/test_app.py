"""Testes de fumaça da interface: o app renderiza sem erros nos principais estados (sem navegador e sem API)."""
import uuid
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from streamlit.testing.v1 import AppTest

import core.graph
from core.graph import app_graph
from tests.test_graph import LLMRoteirizado, SINAIS, chamada

APP = Path(__file__).resolve().parent.parent / "app.py"


def html_renderizado(at: AppTest) -> str:
    """Junta o conteúdo de todos os blocos st.html da página."""
    return "\n".join(str(getattr(el, "proto", el)) for el in at.get("html"))


@pytest.fixture
def com_llm(monkeypatch):
    """Substitui o Gemini por um LLM roteirizado e roda uma conversa numa thread nova."""
    def rodar(respostas, texto):
        llm = LLMRoteirizado(respostas)
        monkeypatch.setattr(core.graph, "_llm_padrao", lambda: llm)
        thread_id = str(uuid.uuid4())
        app_graph.invoke({"messages": [HumanMessage(content=texto)]},
                         config={"configurable": {"thread_id": thread_id}})
        return thread_id
    return rodar


def abrir(thread_id=None, pagina="paginas/triagem.py") -> AppTest:
    """Abre o app (que começa no Plantão) e, por padrão, vai para a página de triagem."""
    at = AppTest.from_file(str(APP), default_timeout=30)
    if thread_id:
        at.session_state["thread_id"] = thread_id
    at.run()
    return at.switch_page(pagina).run() if pagina else at


def linhas_da_fila(at: AppTest) -> list[str]:
    return [b.key.removeprefix("abrir_") for b in at.button if (b.key or "").startswith("abrir_")]


def test_tela_inicial_mostra_saudacao_e_exemplos():
    at = abrir()
    assert not at.exception
    html = html_renderizado(at)
    assert "Aguardando dados" in html and "Eu sou a <b>Clara</b>" in html
    rotulos = [b.label for b in at.button]
    assert "Adulto com dor no peito" in rotulos and "Novo paciente" in rotulos


def test_paciente_classificado_mostra_faixa_e_sinais(com_llm):
    thread_id = com_llm([
        chamada("calcular_escore_gravidade", SINAIS),
        AIMessage(content="Classificação VERMELHO."),
    ], "Dor no peito, 60 anos, FC 120...")
    at = abrir(thread_id)

    assert not at.exception
    html = html_renderizado(at)
    assert "VERMELHO · Emergência" in html
    assert "Sinal de alarme: Dor torácica" in html
    assert "7/7 coletados" in html and "+2 pontos" in html
    assert "✓ Escore NEWS2" in html
    assert [e.label for e in at.expander] == ["Ver detalhes das consultas"]


def test_aprovacao_pendente_mostra_cartao_e_bloqueia_chat(com_llm):
    thread_id = com_llm([
        chamada("acionar_equipe_emergencia", {"motivo": "Dor no peito", "especialidade": "Cardiologia"}),
    ], "Dor no peito")
    at = abrir(thread_id)

    assert not at.exception
    assert "Autorização necessária" in html_renderizado(at)
    assert "Aprovar" in [b.label for b in at.button]
    assert at.chat_input[0].disabled


@pytest.mark.parametrize("modulo", ["ui.componentes", "ui.plantao"])
def test_css_nao_tem_sinal_de_menor(modulo):
    # O st.html usa DOMPurify, que descarta o <style> inteiro se o CSS contiver "<"
    import importlib
    css = importlib.import_module(modulo).CSS
    corpo = css.strip().removeprefix("<style>").removesuffix("</style>")
    assert "<" not in corpo


def test_plantao_abre_primeiro_com_indicadores_leitos_e_equipe():
    at = abrir(pagina=None)
    assert not at.exception
    html = html_renderizado(at)
    assert "Visão geral do hospital" in html
    assert "Pacientes na fila" in html and "Leitos livres" in html and "Médicos disponíveis" in html
    assert "Lotada" in html  # a Emergência simulada está sem vagas
    assert "Dra. Ana Silva" in html and "Em cirurgia" in html


def test_paciente_triado_aparece_na_fila_e_sai_ao_marcar_atendido(com_llm):
    thread_id = com_llm([
        chamada("calcular_escore_gravidade", SINAIS),
        AIMessage(content="Classificação VERMELHO."),
    ], "Falta de ar, 60 anos")
    at = abrir(pagina=None)
    assert thread_id in linhas_da_fila(at)
    assert f"#{thread_id[:6].upper()}" in html_renderizado(at)

    at.button(key=f"atendido_{thread_id}").click().run()
    assert not at.exception
    assert thread_id not in linhas_da_fila(at)


def test_abrir_paciente_da_fila_leva_para_a_triagem(com_llm):
    thread_id = com_llm([
        chamada("calcular_escore_gravidade", SINAIS),
        AIMessage(content="Classificação VERMELHO."),
    ], "Falta de ar, 60 anos")
    at = abrir(pagina=None)
    at.button(key=f"abrir_{thread_id}").click().run()

    assert not at.exception
    assert at.session_state["thread_id"] == thread_id
    assert "VERMELHO · Emergência" in html_renderizado(at)
