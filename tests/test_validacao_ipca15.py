import dataclasses

import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.validate.ipca15 import carregar_configuracao, carregar_excecoes, validar

IPCA15 = carregar_catalogo().indices["ipca15"]
ARMAZEM = ArmazemRaw(IPCA15.fonte)


@pytest.fixture(scope="module")
def staging(dados_dim, dados_fato, dados_referencia):
    dim = dados_dim
    fato = dados_fato
    referencia = dados_referencia
    return fato, referencia, carregar_configuracao(IPCA15, ARMAZEM, dim)


def _rodar(fato, referencia, configuracao):
    resultados, sentinelas = validar(fato, referencia, configuracao)
    return {r.validacao: r for r in resultados}, sentinelas


def _detectado(staging, fato=None, referencia=None):
    """Um erro é detectado se alguma validação falha ou se uma sentinela muda a contagem."""
    base_fato, base_referencia, configuracao = staging
    resultados, sentinelas = _rodar(
        base_fato if fato is None else fato,
        base_referencia if referencia is None else referencia,
        configuracao,
    )
    return any(not r.ok for r in resultados.values()) or not sentinelas.empty


def _alterar(df, filtro, coluna, delta):
    alterado = df.copy()
    alterado.loc[filtro(alterado), coluna] += delta
    return alterado


def test_dados_reais_passam_em_todas_as_validacoes(staging):
    resultados, _ = _rodar(*staging)
    assert {nome: r.exemplos for nome, r in resultados.items() if not r.ok} == {}


def test_toda_excecao_cobre_exatamente_as_falhas_registradas(staging):
    # Sentinela (A-015): se o IBGE corrigir um dado ou surgir erro novo no escopo, a contagem muda.
    _, sentinelas = _rodar(*staging)
    assert sentinelas.empty, sentinelas[["validacao", "tabela_sidra", "codigo_ibge", "obtidas"]]


def test_sem_excecoes_os_casos_conhecidos_aparecem(staging):
    fato, referencia, configuracao = staging
    vazia = dataclasses.replace(configuracao, excecoes=carregar_excecoes(IPCA15).iloc[0:0])
    resultados, _ = _rodar(fato, referencia, vazia)
    assert resultados["reconciliacao"].falhas == 228  # 224 da cesta variável da 1646 + 4 da fonte
    assert resultados["pesos_grupos"].falhas == 2  # 1387, 2010-07 e 2010-08
    assert resultados["costura_acum_6m"].falhas == 3  # 3065: 2006-04, 2011-11, 2012-11
    assert resultados["costura_acum_3m"].falhas == 1  # 3065: 2012-11


def _na(tabela, mes, codigo):
    return lambda df: (df.tabela_sidra == tabela) & (df.mes == mes) & (df.codigo_ibge == codigo)


@pytest.mark.parametrize(
    ("filtro", "coluna", "delta"),
    [
        (_na(7062, "2024-05", "1101002"), "variacao_mensal", 0.5),
        (_na(7062, "2024-05", "1101002"), "peso", 0.01),
        (_na(7062, "2024-05", "1101002"), "variacao_acum_ano", 0.1),
        (_na(7062, "2024-05", "1101002"), "variacao_acum_12m", 0.1),
        (_na(7062, "2024-01", "0"), "variacao_acum_ano", 0.012),  # janeiro: igualdade exata
        (_na(7062, "2024-05", "0"), "variacao_mensal", 0.01),
        (_na(1387, "2009-05", "1101002"), "variacao_acum_ano", 0.10),  # tabela antiga, subitem
        (_na(1387, "2009-05", "1101"), "variacao_acum_ano", 0.05),  # tabela antiga, item
        (_na(1646, "2003-02", "1"), "peso", 0.01),
    ],
)
def test_erro_injetado_no_fato_e_detectado(staging, filtro, coluna, delta):
    assert _detectado(staging, fato=_alterar(staging[0], filtro, coluna, delta))


@pytest.mark.parametrize(
    ("mes", "coluna", "delta"),
    [
        ("2006-04", "variacao_acum_3m", 0.5),  # mês com exceção só na 1119: a 1118 segue validada
        ("2006-04", "variacao_acum_12m", 1.0),
        ("2015-03", "variacao_acum_ano", 0.05),
        ("2015-03", "numero_indice", 1.0),
    ],
)
def test_erro_injetado_na_referencia_e_detectado(staging, mes, coluna, delta):
    referencia = _alterar(staging[1], lambda df: df.mes == mes, coluna, delta)
    assert _detectado(staging, referencia=referencia)


def test_correcao_da_fonte_e_avisada_pela_sentinela(staging):
    fato, referencia, configuracao = staging
    # Simula o IBGE corrigindo a escala dos pesos da 1387 em 2010-07.
    corrigido = fato.copy()
    filtro = (corrigido.tabela_sidra == 1387) & (corrigido.mes == "2010-07")
    corrigido.loc[filtro & (corrigido.codigo_ibge != "0"), "peso"] /= 1.000999
    resultados, sentinelas = _rodar(corrigido, referencia, configuracao)
    assert resultados["pesos_grupos"].ok
    assert (sentinelas.validacao == "pesos_grupos").any()


def test_mes_ou_categoria_ausente_quebra_a_continuidade(staging):
    fato, referencia, configuracao = staging
    sem_mes = fato[~((fato.tabela_sidra == 7062) & (fato.mes == "2024-05"))]
    assert not _rodar(sem_mes, referencia, configuracao)[0]["continuidade"].ok
    sem_categoria = fato[~((fato.tabela_sidra == 1705) & (fato.codigo_ibge == "1101002"))]
    assert not _rodar(sem_categoria, referencia, configuracao)[0]["continuidade"].ok


def test_pai_ausente_e_falha_e_nao_some_do_relatorio(staging):
    fato, referencia, configuracao = staging
    sem_pai = fato[
        ~((fato.tabela_sidra == 7062) & (fato.mes == "2024-05") & (fato.codigo_ibge == "1101"))
    ]
    resultado = _rodar(sem_pai, referencia, configuracao)[0]["pesos_filhos"]
    assert resultado.ausentes == 1 and not resultado.ok


def test_peso_zero_fora_da_cesta_variavel_falha(staging):
    fato, referencia, configuracao = staging
    alterado = fato.copy()
    alterado.loc[(alterado.tabela_sidra == 1705) & (alterado.codigo_ibge == "1101002"), "peso"] = (
        0.0
    )
    assert not _rodar(alterado, referencia, configuracao)[0]["pesos_zero"].ok


def test_variacao_implausivel_falha_no_esquema(staging):
    fato, referencia, configuracao = staging
    alterado = fato.copy()
    alterado.loc[(alterado.codigo_ibge == "1") & (alterado.mes == "2024-05"), "variacao_mensal"] = (
        60.0
    )
    assert not _rodar(alterado, referencia, configuracao)[0]["esquema"].ok


def test_configuracao_vem_do_catalogo(staging):
    configuracao = staging[2]
    assert configuracao.tabela_referencia == 3065
    assert configuracao.meses_esperados[1705][0] == "2012-02"
    assert configuracao.meses_esperados[1705][-1] == "2020-01"
    assert set(configuracao.limites.tabela_sidra) == {1646, 1387}
