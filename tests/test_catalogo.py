import copy

import pytest
import yaml

from macroaf.catalogo import (
    CAMINHO_PADRAO,
    RAIZ,
    ErroCatalogo,
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
    # A troca de POF chega ao IPCA-15 um mês depois do IPCA (lição A-007).
    ipca15 = catalogo.indices["ipca15"]
    assert [(t.tabela, t.versao_pof, t.inicio) for t in ipca15.tabelas_dados] == [
        (1646, "1995-96", "2000-05"),
        (1387, "2002-03", "2006-08"),
        (1705, "2008-09", "2012-02"),
        (7062, "2017-18", "2020-02"),
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


def _ipca15(bruto):
    return bruto["indices"]["ipca15"]


@pytest.mark.parametrize(
    ("alteracao", "mensagem"),
    [
        (lambda b: _tabela(b, 1387).update(inicio="2006-09"), "lacuna"),
        (lambda b: _tabela(b, 1387).update(inicio="2006-07"), "sobreposição"),
        (lambda b: _tabela(b, 1705).update(fim=None), "em aberto"),
        (lambda b: _tabela(b, 7062).update(versao_pof="2008-09"), "POF repetida"),
        (lambda b: _tabela(b, 7062)["variaveis"].append(9999), "não descritas"),
        (lambda b: _tabela(b, 7062).update(papel="outro"), "papel inválido"),
        (lambda b: _tabela(b, 1646).update(fim="2000-01"), "fim anterior"),
        (lambda b: _tabela(b, 1646).update(tabela="abc"), "não numérico"),
        (lambda b: _tabela(b, 1646).update(inicio="2000-5"), "período inválido"),
        (lambda b: _tabela(b, 3065).update(inicio="2001-01"), "não cobre"),
        (lambda b: _tabela(b, 3065).update(fim="2025-12"), "não cobre"),
        (lambda b: _ipca15(b)["tabelas"].append(dict(_tabela(b, 3065))), "tabela repetida"),
        (
            lambda b: _ipca15(b).update(
                tabelas=[t for t in _ipca15(b)["tabelas"] if t["papel"] != "dados"]
            ),
            "nenhuma tabela de dados",
        ),
        (lambda b: _ipca15(b)["variaveis"][356].update(nome="peso"), "nomes de variável"),
        (lambda b: _ipca15(b).update(frequencia="trimestral"), "frequência inválida"),
        (lambda b: _ipca15(b).pop("ficha"), "campo obrigatório ausente: ficha"),
        (lambda b: _ipca15(b).update(variaveis=[355, 356]), "variaveis deve ser dict"),
        (lambda b: b.update(fontes=["ibge_sidra"]), "fontes deve ser dict"),
        (lambda b: _ipca15(b).update(fonte="bcb"), "fonte desconhecida"),
        (lambda b: b.update(versao_esquema=2), "versao_esquema"),
    ],
)
def test_catalogo_invalido_e_rejeitado(bruto, tmp_path, alteracao, mensagem):
    alterado = copy.deepcopy(bruto)
    alteracao(alterado)
    caminho = tmp_path / "series.yaml"
    caminho.write_text(yaml.safe_dump(alterado, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ErroCatalogo, match=mensagem):
        carregar_catalogo(caminho)


def test_fonte_sem_api_de_metadados_e_aceita(bruto, tmp_path):
    del bruto["fontes"]["ibge_sidra"]["api_metadados"]
    caminho = tmp_path / "series.yaml"
    caminho.write_text(yaml.safe_dump(bruto, allow_unicode=True), encoding="utf-8")
    assert carregar_catalogo(caminho).fontes["ibge_sidra"].api_metadados is None
