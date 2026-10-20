from pathlib import Path

import pytest
import yaml

from macroaf import pipeline
from macroaf.catalogo import RAIZ
from macroaf.extract.atualizar import Relatorio


@pytest.fixture
def etapas(monkeypatch, tmp_path):
    """Substitui as etapas por registros de chamada (sem rede e sem gravar no repositório)."""
    chamadas = []
    saida = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(saida))

    def etapa(nome, retorno=0):
        def registrar(*args, **kwargs):
            chamadas.append(nome)
            return retorno

        return registrar

    monkeypatch.setattr(pipeline.harmonizacao, "main", etapa("harmonizacao"))
    monkeypatch.setattr(pipeline.publicar, "publicar", etapa("publicar", []))
    monkeypatch.setattr(pipeline.transformacoes, "main", etapa("pagina"))
    monkeypatch.setattr(pipeline.revisao, "main", etapa("revisao"))
    return chamadas, saida, monkeypatch


def _extracao(monkeypatch, codigo=0, novos=0, revisados=0):
    relatorio = None
    if codigo == 0:
        relatorio = Relatorio(
            novos={7062: ["2026-10"] * novos} if novos else {},
            revisados={7062: ["2026-09"] * revisados} if revisados else {},
        )
    monkeypatch.setattr(pipeline.atualizar, "extrair", lambda *a, **k: (codigo, relatorio))


def test_sem_novidade_nao_publica(etapas):
    chamadas, saida, monkeypatch = etapas
    _extracao(monkeypatch)
    assert pipeline.executar("ipca15") == 0
    assert chamadas == []
    assert saida.read_text() == "publicar=false\n"


@pytest.mark.parametrize(("novos", "revisados"), [(1, 0), (0, 1)])
def test_mes_novo_ou_revisado_publica_tudo_em_ordem(etapas, novos, revisados):
    chamadas, saida, monkeypatch = etapas
    _extracao(monkeypatch, novos=novos, revisados=revisados)
    assert pipeline.executar("ipca15") == 0
    assert chamadas == ["harmonizacao", "publicar", "pagina", "revisao"]
    assert saida.read_text() == "publicar=true\n"


def test_forcar_publica_sem_novidade(etapas):
    chamadas, _, monkeypatch = etapas
    _extracao(monkeypatch)
    assert pipeline.executar("ipca15", forcar=True) == 0
    assert "publicar" in chamadas


@pytest.mark.parametrize("codigo", [1, 2])
def test_falha_da_extracao_para_tudo(etapas, codigo):
    chamadas, _, monkeypatch = etapas
    _extracao(monkeypatch, codigo=codigo)
    assert pipeline.executar("ipca15") == codigo
    assert chamadas == []


def test_publicacao_bloqueada_nao_regera_paginas(etapas):
    chamadas, saida, monkeypatch = etapas
    _extracao(monkeypatch, novos=1)
    monkeypatch.setattr(pipeline.publicar, "publicar", lambda *a: ["validação x falhou"])
    assert pipeline.executar("ipca15") == 1
    assert chamadas == ["harmonizacao"]
    assert not Path(saida).exists()


def test_workflow_so_faz_commit_depois_dos_testes():
    workflow = yaml.safe_load((RAIZ / ".github/workflows/atualizacao.yml").read_text())
    gatilhos = workflow[True]  # o YAML lê a chave "on" como booleano
    assert "schedule" in gatilhos and "workflow_dispatch" in gatilhos
    assert workflow["permissions"] == {"contents": "write"}
    passos = [p.get("name", "") for p in workflow["jobs"]["atualizar"]["steps"]]
    assert passos.index(
        "Testes (marts e páginas em dia, indicadores contra o IBGE)"
    ) < passos.index("Commit e push na main")
