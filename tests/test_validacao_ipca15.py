import pandas as pd
import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.transform.classificacao import montar_dim_classificacao
from macroaf.transform.ipca15 import montar_fato, montar_referencia
from macroaf.validate.ipca15 import carregar_excecoes, validar

IPCA15 = carregar_catalogo().indices["ipca15"]
ARMAZEM = ArmazemRaw(IPCA15.fonte)
MESES = {t.tabela: ARMAZEM.periodos(t.tabela) for t in IPCA15.tabelas_dados}


@pytest.fixture(scope="module")
def staging():
    dim = montar_dim_classificacao(IPCA15, ARMAZEM)
    return montar_fato(IPCA15, ARMAZEM, dim), montar_referencia(IPCA15, ARMAZEM)


def _por_nome(resultados):
    return {r.validacao: r for r in resultados}


def test_dados_reais_passam_em_todas_as_validacoes(staging):
    resultados, _ = validar(*staging, MESES)
    falhas = {r.validacao: r.exemplos for r in resultados if not r.ok}
    assert falhas == {}


def test_toda_excecao_ainda_cobre_uma_falha(staging):
    # Sentinela (A-015): se a fonte corrigir um dado, a exceção deixa de ser usada e o teste avisa.
    _, sem_uso = validar(*staging, MESES)
    assert sem_uso.empty, sem_uso[["validacao", "tabela_sidra", "codigo_ibge", "mes_inicio"]]


def test_toda_excecao_tem_tipo_justificativa_e_aprendizado():
    excecoes = carregar_excecoes()
    assert set(excecoes.tipo) <= {"estrutural", "fonte"}
    assert excecoes.aprendizado.str.fullmatch(r"A-\d{3}").all()


def test_sem_excecoes_os_erros_da_fonte_aparecem(staging):
    vazias = carregar_excecoes().iloc[0:0]
    resultados = _por_nome(validar(*staging, MESES, excecoes=vazias)[0])
    assert resultados["reconciliacao"].falhas == 228  # 224 da cesta variável da 1646 + 4 da fonte
    assert resultados["pesos_grupos"].falhas == 2  # 1387, 2010-07 e 2010-08
    assert resultados["costura_acumulados"].falhas == 4  # 3065: 1118/1119 em 3 meses


@pytest.mark.parametrize(
    ("mudanca", "validacao"),
    [
        (dict(codigo_ibge="1101002", coluna="variacao_mensal", delta=0.5), "reconciliacao"),
        (dict(codigo_ibge="1101002", coluna="peso", delta=0.01), "pesos_filhos"),
        (dict(codigo_ibge="1101002", coluna="variacao_acum_ano", delta=0.1), "acumulado_ano"),
        (dict(codigo_ibge="0", coluna="variacao_mensal", delta=0.01), "costura_mensal"),
    ],
)
def test_erro_injetado_e_detectado(staging, mudanca, validacao):
    fato, referencia = staging
    alterado = fato.copy()
    linha = (
        (alterado.tabela_sidra == 7062)
        & (alterado.mes == "2024-05")
        & (alterado.codigo_ibge == mudanca["codigo_ibge"])
    )
    alterado.loc[linha, mudanca["coluna"]] += mudanca["delta"]
    resultados = _por_nome(validar(alterado, referencia, MESES)[0])
    assert not resultados[validacao].ok


def test_mes_ausente_quebra_a_continuidade(staging):
    fato, referencia = staging
    sem_mes = fato[~((fato.tabela_sidra == 7062) & (fato.mes == "2024-05"))]
    resultados = _por_nome(validar(sem_mes, referencia, MESES)[0])
    assert not resultados["continuidade"].ok


def test_peso_zero_fora_da_cesta_variavel_falha(staging):
    fato, referencia = staging
    alterado = fato.copy()
    alterado.loc[(alterado.tabela_sidra == 1705) & (alterado.codigo_ibge == "1101002"), "peso"] = (
        0.0
    )
    resultados = _por_nome(validar(alterado, referencia, MESES)[0])
    assert not resultados["pesos_zero"].ok


def test_variacao_implausivel_falha_no_esquema(staging):
    fato, referencia = staging
    alterado = fato.copy()
    alterado.loc[(alterado.codigo_ibge == "1") & (alterado.mes == "2024-05"), "variacao_mensal"] = (
        60.0
    )
    assert not _por_nome(validar(alterado, referencia, MESES)[0])["esquema"].ok


def test_excecao_por_padrao_de_codigo_e_faixa_de_meses(staging):
    fato, referencia = staging
    excecoes = pd.DataFrame(
        [
            dict(
                validacao="reconciliacao",
                tabela_sidra=1646,
                codigo_ibge="110[356]",
                mes_inicio="2000-05",
                mes_fim="2000-05",
                tipo="estrutural",
                justificativa="teste",
                aprendizado="A-013",
            )
        ]
    )
    resultados = _por_nome(validar(fato, referencia, MESES, excecoes=excecoes)[0])
    assert resultados["reconciliacao"].excecoes_aplicadas == 3
