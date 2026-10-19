import copy

import pytest
import yaml

from macroaf.catalogo import (
    CAMINHO_PADRAO,
    RAIZ,
    ErroCatalogo,
    _montar_catalogo,
    carregar_catalogo,
    periodo_em_meses,
)


@pytest.fixture(scope="module")
def catalogo():
    return carregar_catalogo()


@pytest.fixture
def bruto():
    with CAMINHO_PADRAO.open(encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def test_catalogo_do_repositorio_e_valido(catalogo):
    assert "ipca15" in catalogo.indices


def test_fichas_citadas_existem(catalogo):
    fichas = [f.ficha for f in catalogo.fontes.values()]
    fichas += [i.ficha for i in catalogo.indices.values()]
    for ficha in fichas:
        assert (RAIZ / ficha).is_file(), ficha


def test_ipca15_tabelas_e_pofs(catalogo):
    ipca15 = catalogo.indices["ipca15"]
    assert [(t.tabela, t.versao_pof) for t in ipca15.tabelas_dados] == [
        (1646, "1995-96"),
        (1387, "2002-03"),
        (1705, "2008-09"),
        (7062, "2017-18"),
    ]
    assert [t.tabela for t in ipca15.tabelas_referencia] == [3065]


def test_ipca15_referencia_cobre_toda_a_serie(catalogo):
    ipca15 = catalogo.indices["ipca15"]
    referencia = ipca15.tabelas_referencia[0]
    assert referencia.inicio == ipca15.tabelas_dados[0].inicio == "2000-05"
    assert referencia.fim is None
    assert referencia.classificacao is None


def test_ipca15_variaveis_do_fato(catalogo):
    # Colunas de fato_ipca15 (PLANEJAMENTO.md, 4.2) presentes em todas as tabelas de dados.
    ipca15 = catalogo.indices["ipca15"]
    nomes = {v.codigo: v.nome for v in ipca15.variaveis.values()}
    for tabela in ipca15.tabelas_dados:
        colunas = {nomes[v] for v in tabela.variaveis}
        assert {"variacao_mensal", "variacao_acum_ano", "peso"} <= colunas


def test_periodo_em_meses():
    assert periodo_em_meses("2000-12") + 1 == periodo_em_meses("2001-01")
    with pytest.raises(ErroCatalogo):
        periodo_em_meses("2000-13")


def _tabela(bruto, numero):
    return next(t for t in bruto["indices"]["ipca15"]["tabelas"] if t["tabela"] == numero)


@pytest.mark.parametrize(
    ("alteracao", "mensagem"),
    [
        (lambda b: _tabela(b, 1387).update(inicio="2006-09"), "lacuna"),
        (lambda b: _tabela(b, 1387).update(inicio="2006-07"), "lacuna"),
        (lambda b: _tabela(b, 1705).update(fim=None), "em aberto"),
        (lambda b: _tabela(b, 7062).update(versao_pof="2008-09"), "POF repetida"),
        (lambda b: _tabela(b, 7062)["variaveis"].append(9999), "não descritas"),
        (lambda b: _tabela(b, 7062).update(papel="outro"), "papel inválido"),
        (lambda b: _tabela(b, 1646).update(fim="2000-01"), "fim anterior"),
        (lambda b: b["indices"]["ipca15"].update(fonte="bcb"), "fonte desconhecida"),
        (lambda b: b.update(versao_esquema=2), "versao_esquema"),
    ],
)
def test_catalogo_invalido_e_rejeitado(bruto, alteracao, mensagem):
    alterado = copy.deepcopy(bruto)
    alteracao(alterado)
    with pytest.raises(ErroCatalogo, match=mensagem):
        _montar_catalogo(alterado)
