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


def abrir(thread_id=None) -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=30)
    if thread_id:
        at.session_state["thread_id"] = thread_id
    return at.run()


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


def test_css_nao_tem_sinal_de_menor():
    # O st.html usa DOMPurify, que descarta o <style> inteiro se o CSS contiver "<"
    from ui.componentes import CSS
    corpo = CSS.strip().removeprefix("<style>").removesuffix("</style>")
    assert "<" not in corpo
