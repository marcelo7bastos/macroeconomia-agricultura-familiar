from itertools import pairwise

import numpy as np
import pandas as pd
import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.indicators.indice import (
    acumulado,
    acumulado_no_ano,
    marcar_cesta_variavel,
    montar_indice,
    rebasear,
)
from macroaf.validate.ipca15 import MEIA_CASA_VARIACAO, carregar_excecoes

IPCA15 = carregar_catalogo().indices["ipca15"]
INICIO_TABELA = {t.tabela: t.inicio for t in IPCA15.tabelas_dados}
ANTERIOR = {nova: antiga for antiga, nova in pairwise(t.tabela for t in IPCA15.tabelas_dados)}


def _longa_de_brinquedo(series: dict[str, list[float]], inicio="2020-01") -> pd.DataFrame:
    linhas = []
    for serie_id, variacoes in series.items():
        meses = pd.period_range(inicio, periods=len(variacoes), freq="M").strftime("%Y-%m")
        for mes, v in zip(meses, variacoes, strict=True):
            linhas.append(
                {
                    "serie_id": serie_id,
                    "mes": mes,
                    "tabela_sidra": 1,
                    "codigo_sidra": 1,
                    "codigo_ibge": "0",
                    "nivel_hierarquico": "geral",
                    "variacao_mensal": v,
                }
            )
    return pd.DataFrame(linhas)


def test_indice_encadeia_e_recomeca_em_cada_serie():
    indice = montar_indice(_longa_de_brinquedo({"a": [10.0, -10.0, 5.0], "b": [1.0]}))
    assert indice.indice.tolist() == pytest.approx([110.0, 99.0, 103.95, 101.0])
    assert not indice.cesta_variavel.any()


def test_acumulado_usa_a_base_na_primeira_janela_completa():
    indice = montar_indice(_longa_de_brinquedo({"a": [10.0, -10.0, 5.0]}))
    assert acumulado(indice, 2).tolist() == pytest.approx([np.nan, -1.0, -5.5], nan_ok=True)
    assert acumulado(indice, 3).iloc[2] == pytest.approx(3.95)


def test_acumulado_no_ano_so_com_janeiro_na_serie():
    indice = montar_indice(
        _longa_de_brinquedo({"a": [1.0, 1.0, 2.0], "b": [1.0, 2.0]}, inicio="2020-12")
    )
    assert acumulado_no_ano(indice).tolist() == pytest.approx(
        [np.nan, 1.0, 3.02, np.nan, 2.0], nan_ok=True
    )


def test_rebase_e_uma_divisao():
    indice = montar_indice(_longa_de_brinquedo({"a": [10.0, -10.0], "b": [5.0]}))
    assert rebasear(indice, "2020-02").tolist() == pytest.approx(
        [110 / 99 * 100, 100.0, np.nan], nan_ok=True
    )


@pytest.mark.parametrize(
    ("variacoes", "inicio"),
    [([1.0, -100.0], "2020-01"), ([1.0, np.nan], "2020-01")],
)
def test_variacao_que_nao_encadeia_e_erro(variacoes, inicio):
    with pytest.raises(ValueError, match="não se encadeia"):
        montar_indice(_longa_de_brinquedo({"a": variacoes}, inicio=inicio))


def test_mes_faltando_e_erro():
    longa = _longa_de_brinquedo({"a": [1.0, 2.0, 3.0]}).drop(index=1)
    with pytest.raises(ValueError, match="mês faltando"):
        montar_indice(longa)


@pytest.fixture(scope="module")
def base(dados_longa, dados_referencia):
    longa = dados_longa
    indice = montar_indice(longa, marcar_cesta_variavel(longa, carregar_excecoes(IPCA15)))
    publicados = longa[["serie_id", "mes", "variacao_acum_ano", "variacao_acum_12m"]]
    indice = indice.merge(publicados, on=["serie_id", "mes"], validate="one_to_one")
    return indice, dados_referencia.set_index("mes")


def _limite(indice: pd.DataFrame, calculado: pd.Series, meses: pd.Series) -> pd.Series:
    """Limite analítico (A-014) do acumulado composto de `meses` variações com 2 casas."""
    inverso = 1 / (1 + indice.variacao_mensal / 100)
    acumulados = inverso.groupby(indice.serie_id).cumsum()
    soma = pd.Series(np.nan, index=indice.index)
    for k in sorted(meses.unique()):
        linhas = meses == k
        anterior = acumulados.groupby(indice.serie_id).shift(k).fillna(0)
        soma[linhas] = (acumulados - anterior)[linhas]
    return MEIA_CASA_VARIACAO * (1 + calculado.abs() / 100) * soma + MEIA_CASA_VARIACAO


def test_indice_geral_reproduz_o_numero_indice_da_3065(base):
    indice, referencia = base
    geral = indice[indice.codigo_ibge == "0"].set_index("mes").indice
    assert geral.index.tolist() == referencia.index.tolist()  # uma série só, sem quebra
    oficial = referencia.numero_indice
    desvio = (geral / geral.iloc[0] * oficial.iloc[0] / oficial - 1).abs()
    assert desvio.max() <= 1e-4  # 0,01%


@pytest.mark.parametrize(
    ("meses", "variavel"),
    [(3, "variacao_acum_3m"), (6, "variacao_acum_6m"), (12, "variacao_acum_12m")],
)
def test_acumulados_do_geral_batem_com_a_3065(base, meses, variavel):
    indice, referencia = base
    geral = indice[indice.codigo_ibge == "0"].reset_index(drop=True)
    calculado = acumulado(geral, meses)
    limite = _limite(geral, calculado, pd.Series(meses, index=geral.index))
    erro = (calculado - geral.mes.map(referencia[variavel])).abs()
    falhas = set(geral.mes[erro > limite])
    excecoes = carregar_excecoes(IPCA15)
    erros_da_fonte = excecoes[excecoes.validacao == f"costura_acum_{meses}m"]
    assert falhas == set(erros_da_fonte.mes_inicio)  # A-015: erros publicados na 3065


def test_acumulado_no_ano_do_geral_bate_com_a_3065(base):
    indice, referencia = base
    geral = indice[indice.codigo_ibge == "0"].reset_index(drop=True)
    calculado = acumulado_no_ano(geral)
    limite = _limite(geral, calculado, geral.mes.str[5:].astype(int))
    erro = (calculado - geral.mes.map(referencia.variacao_acum_ano)).abs()
    assert (erro.dropna() <= limite[erro.notna()]).all()


@pytest.fixture(scope="module")
def no_ano(base):
    """Acumulado no ano do índice ao lado da 356, com o que a âncora do IBGE precisa (A-023)."""
    indice, _ = base
    dados = indice.copy()
    dados["calculado"] = acumulado_no_ano(dados)
    dados["limite"] = _limite(dados, dados.calculado, dados.mes.str[5:].astype(int))
    dados["erro"] = (dados.calculado - dados.variacao_acum_ano).abs()
    ano = [dados.serie_id, dados.mes.str[:4]]
    dados["cruza_tabela"] = dados.groupby(ano).tabela_sidra.transform("first") != dados.tabela_sidra
    dados["codigo_em_janeiro"] = dados.groupby(ano).codigo_ibge.transform("first")
    return dados[dados.erro.notna()]


def test_acumulado_no_ano_dentro_das_tabelas_sem_ruido(no_ano):
    # 1646 e 1387 têm 356 com ruído acima do arredondamento (A-016), já tratado na validação.
    dentro = no_ano[~no_ano.cruza_tabela & no_ano.tabela_sidra.isin([1705, 7062])]
    assert len(dentro) > 60_000
    assert (dentro.erro <= dentro.limite).all()


def test_acumulado_no_ano_atravessa_a_troca_quando_o_codigo_continua(no_ano):
    # O IBGE ancora a 356 do ano da troca no mesmo código da tabela anterior (A-023).
    cruza = no_ano[no_ano.cruza_tabela & (no_ano.codigo_ibge == no_ano.codigo_em_janeiro)]
    falhas = cruza[cruza.erro > cruza.limite]
    # Única exceção: subitens in natura que vêm da cesta variável da 1646 (A-013), em 2006.
    assert set(falhas.tabela_sidra) == {1387}
    assert falhas.codigo_ibge.str.fullmatch(r"110[356](\d{3})?").all()
    assert falhas.serie_id.nunique() == 34


def test_codigo_novo_no_ano_da_troca_acumula_desde_a_troca(no_ano):
    # Para código novo, a 356 do ano da troca começa no primeiro mês da tabela nova (A-023).
    novos = no_ano[no_ano.cruza_tabela & (no_ano.codigo_ibge != no_ano.codigo_em_janeiro)]
    assert novos.serie_id.nunique() == 8
    desde_troca = novos.mes >= novos.tabela_sidra.map(INICIO_TABELA)
    assert desde_troca.all()
    fator = 1 + novos.variacao_mensal / 100
    chave = [novos.serie_id, novos.tabela_sidra]
    calculado = (fator.groupby(chave).cumprod() - 1) * 100
    assert ((calculado - novos.variacao_acum_ano).abs() <= novos.limite).all()


def _janeiro_ate_a_troca(indice: pd.DataFrame, tabela: int, codigo: str) -> float:
    """Fator de janeiro até a véspera da troca, pelo código na tabela anterior (NaN se não há)."""
    inicio = INICIO_TABELA[tabela]
    antes = indice[
        (indice.tabela_sidra == ANTERIOR[tabela])
        & (indice.codigo_ibge == codigo)
        & (indice.mes >= inicio[:4] + "-01")
        & (indice.mes < inicio)
    ]
    return float((1 + antes.variacao_mensal / 100).prod()) if len(antes) else np.nan


def _desde_a_troca(linhas: pd.DataFrame) -> pd.Series:
    fator = 1 + linhas.variacao_mensal / 100
    return fator.groupby(linhas.serie_id).cumprod()


def test_serie_quebrada_no_ano_da_troca_tem_356_que_atravessa_a_quebra(base):
    # A 356 encadeia pelo código mesmo onde o projeto marcou quebra (A-023): não é da série.
    indice, _ = base
    inicio = indice.groupby("serie_id").mes.transform("min")
    ano_da_troca = indice.tabela_sidra.map(INICIO_TABELA)
    nascem = indice[
        (inicio == ano_da_troca)
        & (inicio.str[5:] != "01")
        & (indice.mes.str[:4] == inicio.str[:4])
        & indice.tabela_sidra.isin(ANTERIOR)
    ].copy()
    nascem["janeiro"] = [
        _janeiro_ate_a_troca(indice, t, c)
        for t, c in zip(nascem.tabela_sidra, nascem.codigo_ibge, strict=True)
    ]
    quebradas = nascem[nascem.janeiro.notna()]  # código que já existia na tabela anterior
    # 12 séries; em 9101008 (2020) o código ficou parado de janeiro à troca: as regras coincidem.
    assert quebradas.serie_id.nunique() == 12
    assert acumulado_no_ano(indice).loc[quebradas.index].isna().all()
    pelo_codigo = (quebradas.janeiro * _desde_a_troca(quebradas) - 1) * 100
    assert ((pelo_codigo - quebradas.variacao_acum_ano).abs() <= 0.05).all()  # ruído A-016


# Código novo na 1387 cuja 356 de 2006 o IBGE ancorou num antecessor de outro código (A-023).
ANCORAS_1387 = {
    "8104": "8101014",  # Cursos diversos: item novo ← subitem Cursos diversos
    **{f"8104{n:03d}": "8101014" for n in range(1, 10)},
    "1110010": "1110011",  # Frango em pedaços ← Peito de frango
    "1111011": "1111024",  # Queijo ← Queijo prato
}


def test_ancora_escolhida_pelo_ibge_na_troca_para_a_1387(base):
    indice, _ = base
    linhas = indice[
        (indice.tabela_sidra == 1387)
        & (indice.mes.str[:4] == "2006")
        & indice.codigo_ibge.isin(ANCORAS_1387)
    ].copy()
    assert linhas.codigo_ibge.nunique() == 12
    janeiro = linhas.codigo_ibge.map(
        {c: _janeiro_ate_a_troca(indice, 1387, a) for c, a in ANCORAS_1387.items()}
    )
    pelo_antecessor = (janeiro * _desde_a_troca(linhas) - 1) * 100
    assert ((pelo_antecessor - linhas.variacao_acum_ano).abs() <= 0.05).all()


def test_acumulado_12m_bate_com_a_1120(base):
    indice, _ = base
    calculado = acumulado(indice, 12)
    limite = _limite(indice, calculado, pd.Series(12, index=indice.index))
    erro = (calculado - indice.variacao_acum_12m).abs()
    comparaveis = erro.notna()
    assert comparaveis.sum() > 45_000
    assert (erro[comparaveis] <= limite[comparaveis]).all()


def test_cesta_variavel_marcada_so_na_1646_in_natura(base):
    indice, _ = base
    marcadas = indice[indice.cesta_variavel]
    assert set(marcadas.tabela_sidra) == {1646}
    assert marcadas.codigo_ibge.str.fullmatch(r"110[356]\d{3}").all()
