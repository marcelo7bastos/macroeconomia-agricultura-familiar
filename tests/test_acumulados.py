import numpy as np
import pandas as pd
import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.indicators.acumulados import (
    JANELAS,
    limite_acumulado,
    montar_acumulados,
    tamanho_da_janela,
)
from macroaf.indicators.indice import (
    acumulado,
    acumulado_no_ano,
    marcar_cesta_variavel,
    montar_indice,
)
from macroaf.transform.classificacao import montar_dim_classificacao
from macroaf.transform.harmonizacao import ler_mapa, montar_serie_longa
from macroaf.transform.ipca15 import montar_fato, montar_referencia
from macroaf.validate.ipca15 import carregar_excecoes

IPCA15 = carregar_catalogo().indices["ipca15"]
ARMAZEM = ArmazemRaw(IPCA15.fonte)
REFERENCIA = next(t.tabela for t in IPCA15.tabelas if t.papel == "referencia")
SEM_EXCECOES = carregar_excecoes(IPCA15).iloc[0:0]


def _longa(series: dict[str, tuple[str, list[float]]], entrada="novo") -> pd.DataFrame:
    linhas = []
    for serie_id, (inicio, variacoes) in series.items():
        meses = pd.period_range(inicio, periods=len(variacoes), freq="M").strftime("%Y-%m")
        for mes, v in zip(meses, variacoes, strict=True):
            linhas.append(
                {
                    "serie_id": serie_id,
                    "mes": mes,
                    "tabela_sidra": 1,
                    "codigo_sidra": 1,
                    "codigo_ibge": "1101001",
                    "nivel_hierarquico": "subitem",
                    "variacao_mensal": v,
                    "variacao_acum_ano": np.nan,
                    "variacao_acum_12m": np.nan,
                    "entrada": entrada,
                }
            )
    return pd.DataFrame(linhas)


def _acumulados(longa: pd.DataFrame) -> pd.DataFrame:
    referencia = pd.DataFrame({"mes": longa.mes.unique()})
    for coluna in ["variacao_acum_3m", "variacao_acum_6m", "variacao_acum_12m"]:
        referencia[coluna] = np.nan
    referencia["variacao_acum_ano"] = np.nan
    return montar_acumulados(montar_indice(longa), longa, referencia, SEM_EXCECOES, 0)


def test_janela_que_sai_da_serie_fica_vazia():
    resultado = _acumulados(_longa({"a": ("2020-01", [1.0, 1.0]), "b": ("2020-03", [2.0])}))
    tres = resultado[resultado.janela == "3m"]
    assert tres.empty
    ano = resultado[resultado.janela == "ano"].set_index(["serie_id", "mes"]).acumulado
    assert ano.to_dict() == pytest.approx({("a", "2020-01"): 1.0, ("a", "2020-02"): 2.01})
    assert set(resultado.origem) == {"calculado"}


def test_oficial_e_preferido_e_marcado():
    longa = _longa({"a": ("2020-01", [1.0, 1.0])})
    longa["variacao_acum_ano"] = [1.0, 2.0]  # 2,0 publicado; 2,01 calculado
    resultado = _acumulados(longa)
    ano = resultado[resultado.janela == "ano"]
    assert ano.acumulado.tolist() == [1.0, 2.0]
    assert set(ano.origem) == {"oficial"}


def test_oficial_do_ano_nao_atravessa_quebra():
    # Série que começa em março: a 356 publicada cobriria janeiro e fevereiro de outra série.
    longa = _longa({"a": ("2020-03", [1.0, 1.0])})
    longa["variacao_acum_ano"] = [5.0, 6.0]
    assert _acumulados(longa)[lambda d: d.janela == "ano"].empty


def test_oficial_antes_do_inicio_dos_dados_vale():
    longa = _longa({"a": ("2000-05", [1.0])}, entrada="inicio dos dados")
    longa["variacao_acum_ano"] = [3.0]
    ano = _acumulados(longa)[lambda d: d.janela == "ano"]
    assert ano.acumulado.tolist() == [3.0]
    assert ano.origem.tolist() == ["oficial"]


@pytest.fixture(scope="module")
def base():
    dim = montar_dim_classificacao(IPCA15, ARMAZEM)
    fato = montar_fato(IPCA15, ARMAZEM, dim)
    longa = montar_serie_longa(fato, dim, ler_mapa(IPCA15))
    excecoes = carregar_excecoes(IPCA15)
    indice = montar_indice(longa, marcar_cesta_variavel(longa, excecoes))
    referencia = montar_referencia(IPCA15, ARMAZEM)
    acumulados = montar_acumulados(indice, longa, referencia, excecoes, REFERENCIA)
    return indice, longa, acumulados


def test_uma_linha_por_serie_mes_e_janela(base):
    _, _, acumulados = base
    assert not acumulados.duplicated(["serie_id", "mes", "janela"]).any()
    assert set(acumulados.janela) == set(JANELAS)
    assert set(acumulados.origem) == {"oficial", "calculado"}


def test_janelas_longas_so_calculadas(base):
    _, _, acumulados = base
    longas = acumulados[acumulados.janela.isin(["24m", "36m"])]
    assert set(longas.origem) == {"calculado"}


def test_onde_os_dois_existem_calculado_bate_com_oficial(base):
    # O oficial é o publicado; o calculado pelo índice tem de concordar com ele (A-014), salvo
    # ruído da 356 nas tabelas antigas (A-016), cesta variável (A-013) e erros publicados (A-015).
    indice, _, acumulados = base
    oficiais = acumulados[(acumulados.origem == "oficial") & ~acumulados.cesta_variavel]
    oficiais = oficiais[~oficiais.tabela_sidra.isin([1646, 1387]) | (oficiais.janela != "ano")]
    for janela, linhas in oficiais.groupby("janela"):
        tamanho = tamanho_da_janela(indice, janela)
        if JANELAS[janela] is None:
            calculado = acumulado_no_ano(indice)
        else:
            calculado = acumulado(indice, JANELAS[janela])
        conferir = indice[["serie_id", "mes"]].assign(
            calculado=calculado, limite=limite_acumulado(indice, calculado, tamanho)
        )
        comparar = linhas.merge(conferir, on=["serie_id", "mes"]).dropna(subset=["calculado"])
        assert len(comparar) > 300, janela
        assert ((comparar.acumulado - comparar.calculado).abs() <= comparar.limite).all(), janela


def test_erro_publicado_da_3065_vira_calculado(base):
    _, _, acumulados = base
    geral = acumulados[acumulados.codigo_ibge == "0"].set_index(["janela", "mes"]).origem
    for janela, mes in [("3m", "2012-11"), ("6m", "2006-04"), ("6m", "2011-11"), ("6m", "2012-11")]:
        assert geral[(janela, mes)] == "calculado"
    assert geral[("3m", "2012-10")] == "oficial"


def test_356_trocada_de_2003_02_vira_calculado(base):
    # A-015: 356 de 2003-02 trocada em todas as categorias exceto o geral.
    _, _, acumulados = base
    linhas = acumulados[
        (acumulados.janela == "ano")
        & (acumulados.mes == "2003-02")
        & (acumulados.nivel_hierarquico == "grupo")
    ]
    assert set(linhas.origem) == {"calculado"}


def test_356_no_ano_da_troca_so_onde_mede_a_serie(base):
    # A-023: série que nasce no meio do ano da troca ou que mudou de código no ano não usa a 356.
    _, longa, acumulados = base
    ano = acumulados[acumulados.janela == "ano"]
    inicio = longa.groupby("serie_id").mes.min()
    meio_do_ano = ano[
        (ano.serie_id.map(inicio).str[5:] != "01")
        & (ano.mes.str[:4] == ano.serie_id.map(inicio).str[:4])
        & (ano.serie_id.map(inicio) > "2000-05")
    ]
    assert meio_do_ano.empty
    codigo_janeiro = ano.groupby([ano.serie_id, ano.mes.str[:4]]).codigo_ibge.transform("first")
    mudou = ano[codigo_janeiro != ano.codigo_ibge]
    assert mudou.serie_id.nunique() == 8
    assert set(mudou.origem) == {"calculado"}


def test_cesta_variavel_contamina_as_janelas_seguintes(base):
    _, _, acumulados = base
    marcadas = acumulados[acumulados.cesta_variavel]
    doze = marcadas[marcadas.janela == "12m"]
    assert doze.mes.max() == "2007-06"  # último mês cuja janela de 12 meses inclui jul/2006
    ano_2006 = marcadas[(marcadas.janela == "ano") & (marcadas.tabela_sidra == 1387)]
    assert set(ano_2006.mes.str[:4]) == {"2006"}
