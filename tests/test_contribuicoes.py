import pandas as pd
import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.indicators.acumulados import JANELAS
from macroaf.indicators.contribuicoes import (
    contribuicao_acumulada,
    contribuicao_mensal,
    montar_contribuicoes,
)
from macroaf.indicators.indice import (
    acumulado,
    acumulado_no_ano,
    marcar_cesta_variavel,
    montar_indice,
)
from macroaf.transform.classificacao import montar_dim_classificacao
from macroaf.transform.harmonizacao import ler_mapa, montar_serie_longa
from macroaf.transform.ipca15 import montar_fato
from macroaf.validate.ipca15 import MEIA_CASA_PESO, MEIA_CASA_VARIACAO, carregar_excecoes

IPCA15 = carregar_catalogo().indices["ipca15"]
ARMAZEM = ArmazemRaw(IPCA15.fonte)


def test_contribuicao_divide_pela_soma_dos_pesos_dos_grupos():
    dados = pd.DataFrame(
        {
            "mes": ["2020-01"] * 3,
            "tabela_sidra": [1] * 3,
            "codigo_ibge": ["0", "1", "2"],
            "nivel_hierarquico": ["geral", "grupo", "grupo"],
            "peso": [100.0, 40.04, 60.06],  # grupos somam 100,1 (A-015)
            "variacao_mensal": [0.5, 1.0, 0.0],
        }
    )
    assert contribuicao_mensal(dados).tolist() == pytest.approx([0.5, 0.4, 0.0])


@pytest.fixture(scope="module")
def base():
    dim = montar_dim_classificacao(IPCA15, ARMAZEM)
    fato = montar_fato(IPCA15, ARMAZEM, dim)
    longa = montar_serie_longa(fato, dim, ler_mapa(IPCA15))
    indice = montar_indice(longa, marcar_cesta_variavel(longa, carregar_excecoes(IPCA15)))
    return indice, longa, montar_contribuicoes(indice, longa)


def _limite_mensal(longa: pd.DataFrame) -> pd.Series:
    """Limite da reconciliação dos grupos com o geral, por mês (o mesmo da validação, A-014)."""
    grupos = longa[longa.nivel_hierarquico == "grupo"]
    geral = longa[longa.codigo_ibge == "0"].set_index("mes").variacao_mensal
    desvio = (grupos.variacao_mensal - grupos.mes.map(geral)).abs()
    erro_peso = (MEIA_CASA_PESO * desvio).groupby(grupos.mes).sum()
    return 2 * MEIA_CASA_VARIACAO + erro_peso / grupos.groupby("mes").peso.sum()


def _por_janela(contribuicoes: pd.DataFrame, filtro) -> pd.Series:
    linhas = contribuicoes[filtro(contribuicoes)]
    return linhas.groupby(["janela", "mes"]).contribuicao.sum()


def test_soma_dos_grupos_e_a_variacao_do_geral(base):
    _, longa, contribuicoes = base
    grupos = _por_janela(contribuicoes, lambda c: c.nivel_hierarquico == "grupo").loc["mes"]
    geral = longa[longa.codigo_ibge == "0"].set_index("mes").variacao_mensal
    assert ((grupos - geral).abs() <= _limite_mensal(longa) + 1e-9).all()


def test_contribuicao_acumulada_do_geral_e_o_acumulado_do_geral(base):
    indice, _, contribuicoes = base
    geral = indice[indice.codigo_ibge == "0"].reset_index(drop=True)
    publicada = contribuicoes[contribuicoes.codigo_ibge == "0"].set_index(["janela", "mes"])
    for janela, meses in JANELAS.items():
        esperado = acumulado_no_ano(geral) if meses is None else acumulado(geral, meses)
        esperado.index = geral.mes
        obtido = publicada.loc[janela].contribuicao
        assert obtido.to_numpy() == pytest.approx(esperado.dropna().to_numpy(), abs=1e-9)


def test_soma_dos_grupos_reproduz_o_acumulado_do_geral(base):
    # Cada mês difere no máximo pelo limite da reconciliação, reescalado como as contribuições.
    indice, longa, contribuicoes = base
    geral = indice[indice.codigo_ibge == "0"].reset_index(drop=True)
    indice_geral = geral.set_index("mes").indice
    grupos = _por_janela(contribuicoes, lambda c: c.nivel_hierarquico == "grupo")
    do_geral = _por_janela(contribuicoes, lambda c: c.codigo_ibge == "0")
    limite_mes = geral.mes.map(_limite_mensal(longa))
    for janela in JANELAS:
        limite = contribuicao_acumulada(geral, limite_mes, janela, indice_geral)
        limite.index = geral.mes
        diferenca = (grupos.loc[janela] - do_geral.loc[janela]).abs()
        assert (diferenca <= limite.reindex(diferenca.index) + 1e-9).all(), janela


def test_participacao_no_grupo_soma_100(base):
    _, _, contribuicoes = base
    mensais = contribuicoes[
        (contribuicoes.janela == "mes") & contribuicoes.participacao_no_grupo.notna()
    ]
    chave = [
        mensais.mes,
        mensais.tabela_sidra,
        mensais.nivel_hierarquico,
        mensais.codigo_ibge.str[0],
    ]
    soma = mensais.participacao_no_grupo.groupby(chave).sum()
    assert soma.to_numpy() == pytest.approx(100.0)


def test_in_natura_da_1646_so_pelo_item(base):
    # A-013: os pesos dos subitens in natura da 1646 não reproduzem o item.
    _, _, contribuicoes = base
    in_natura = contribuicoes[
        (contribuicoes.tabela_sidra == 1646)
        & contribuicoes.codigo_ibge.str.fullmatch(r"110[356](\d{3})?")
    ]
    assert set(in_natura.nivel_hierarquico) == {"item"}


def test_acumulada_nao_sai_da_serie(base):
    indice, _, contribuicoes = base
    inicio = indice.groupby("serie_id").mes.min()
    doze = contribuicoes[contribuicoes.janela == "12m"]
    meses_desde_o_inicio = (
        pd.PeriodIndex(doze.mes, freq="M") - pd.PeriodIndex(doze.serie_id.map(inicio), freq="M")
    ).map(lambda d: d.n)
    assert (meses_desde_o_inicio >= 11).all()
