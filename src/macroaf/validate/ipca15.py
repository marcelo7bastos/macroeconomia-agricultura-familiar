"""Validações do IPCA-15 (seção 4.4 do planejamento; tolerâncias em METODOLOGIA.md, seção 6).

Cada validação devolve um `Resultado`. Uma falha bloqueia a publicação. Diferenças conhecidas e
explicadas ficam em `reference/excecoes_validacao_ipca15.csv`, cada uma com justificativa e o
A-NNN de origem; nada é ignorado em silêncio.

Uso:

    uv run python -m macroaf.validate.ipca15     # valida o staging e grava validacao.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import pandera.pandas as pa

from macroaf.catalogo import RAIZ, carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.transform.classificacao import NIVEIS
from macroaf.transform.ipca15 import diretorio_staging

CAMINHO_EXCECOES = RAIZ / "reference" / "excecoes_validacao_ipca15.csv"

# Tolerâncias (pontos percentuais ou unidades da variável), calibradas na #5; ver METODOLOGIA.md.
TOLERANCIAS = {
    "pesos_grupos": 0.001,
    "pesos_filhos": 0.005,
    "reconciliacao": 0.02,
    "acumulado_ano": 0.02,
    "acumulado_12m": 0.02,
    "costura_mensal": 0.0,
    "costura_acumulados": 0.02,
    "costura_numero_indice_relativa": 1e-4,
}
VARIACAO_PLAUSIVEL = 50.0

ESQUEMA_FATO = pa.DataFrameSchema(
    {
        "mes": pa.Column(str, pa.Check.str_matches(r"^\d{4}-(0[1-9]|1[0-2])$")),
        "versao_pof": pa.Column(str),
        "tabela_sidra": pa.Column(int),
        "codigo_sidra": pa.Column(int),
        "codigo_ibge": pa.Column(str),
        "nivel_hierarquico": pa.Column(str, pa.Check.isin(NIVEIS)),
        "variacao_mensal": pa.Column(
            float, pa.Check.in_range(-VARIACAO_PLAUSIVEL, VARIACAO_PLAUSIVEL)
        ),
        "variacao_acum_ano": pa.Column(float),
        "variacao_acum_12m": pa.Column(float, nullable=True),
        "peso": pa.Column(float, pa.Check.in_range(0, 100)),
    },
    unique=["mes", "tabela_sidra", "codigo_sidra"],
    strict=True,
)


@dataclass
class Resultado:
    validacao: str
    verificados: int
    falhas: int
    tolerancia: float | None
    excecoes_aplicadas: int = 0
    maior_diferenca: float | None = None
    exemplos: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.falhas == 0


def carregar_excecoes(caminho: Path = CAMINHO_EXCECOES) -> pd.DataFrame:
    colunas = ["validacao", "tabela_sidra", "codigo_ibge", "mes_inicio", "mes_fim"]
    if not caminho.exists():
        return pd.DataFrame(columns=[*colunas, "justificativa", "aprendizado"])
    excecoes = pd.read_csv(caminho, dtype=str)
    excecoes["tabela_sidra"] = excecoes["tabela_sidra"].astype(int)
    vazias = excecoes[excecoes.justificativa.isna() | excecoes.aprendizado.isna()]
    if not vazias.empty:
        raise ValueError(f"exceção sem justificativa ou aprendizado: {vazias.values.tolist()}")
    return excecoes


def _resultado(
    nome: str,
    diferencas: pd.DataFrame,
    tolerancia: float,
    excecoes: pd.DataFrame,
    coluna: str = "diferenca",
) -> Resultado:
    """`diferencas` tem mes, tabela_sidra, codigo_ibge e a coluna de diferença."""
    diferencas = diferencas.dropna(subset=[coluna])
    fora = diferencas[diferencas[coluna].abs() > tolerancia + 1e-9]
    excecoes_da_validacao = excecoes[excecoes.validacao == nome]
    coberto = pd.Series(False, index=fora.index)
    for excecao in excecoes_da_validacao.itertuples():
        coberto |= (
            (fora.tabela_sidra == excecao.tabela_sidra)
            & (fora.codigo_ibge == excecao.codigo_ibge)
            & (fora.mes >= excecao.mes_inicio)
            & (fora.mes <= excecao.mes_fim)
        )
    falhas = fora[~coberto]
    maior = diferencas[coluna].abs().max() if not diferencas.empty else None
    return Resultado(
        validacao=nome,
        verificados=len(diferencas),
        falhas=len(falhas),
        tolerancia=tolerancia,
        excecoes_aplicadas=int(coberto.sum()),
        maior_diferenca=None if maior is None or math.isnan(maior) else round(float(maior), 6),
        exemplos=(
            falhas.reindex(falhas[coluna].abs().sort_values(ascending=False).index)
            .head(5)
            .round(6)
            .to_dict("records")
        ),
    )


def _com_pai(fato: pd.DataFrame) -> pd.DataFrame:
    digitos_pai = {1: 0, 2: 1, 4: 2, 7: 4}

    def pai(codigo: str) -> str | None:
        if codigo == "0":
            return None
        n = digitos_pai[len(codigo)]
        return "0" if n == 0 else codigo[:n]

    return fato.assign(codigo_pai=fato.codigo_ibge.map(pai))


def validar_esquema(fato: pd.DataFrame) -> Resultado:
    try:
        ESQUEMA_FATO.validate(fato, lazy=True)
    except pa.errors.SchemaErrors as erros:
        casos = erros.failure_cases
        return Resultado(
            "esquema", len(fato), len(casos), None, exemplos=casos.head(5).to_dict("records")
        )
    return Resultado("esquema", len(fato), 0, None)


def validar_pesos(fato: pd.DataFrame, excecoes: pd.DataFrame) -> list[Resultado]:
    """Grupos somam 100 e filhos somam o peso do pai, em cada mês e tabela."""
    fato = _com_pai(fato)
    grupos = (
        fato[fato.nivel_hierarquico == "grupo"]
        .groupby(["mes", "tabela_sidra"], as_index=False)
        .peso.sum()
        .assign(codigo_ibge="0")
    )
    grupos["diferenca"] = grupos.peso - 100

    soma = (
        fato[fato.codigo_pai.notna() & (fato.nivel_hierarquico != "grupo")]
        .groupby(["mes", "tabela_sidra", "codigo_pai"], as_index=False)
        .peso.sum()
        .rename(columns={"codigo_pai": "codigo_ibge", "peso": "soma_filhos"})
    )
    filhos = soma.merge(fato[["mes", "tabela_sidra", "codigo_ibge", "peso"]], how="left")
    filhos["diferenca"] = filhos.soma_filhos - filhos.peso
    return [
        _resultado("pesos_grupos", grupos, TOLERANCIAS["pesos_grupos"], excecoes),
        _resultado("pesos_filhos", filhos, TOLERANCIAS["pesos_filhos"], excecoes),
    ]


def validar_reconciliacao(fato: pd.DataFrame, excecoes: pd.DataFrame) -> Resultado:
    """Média dos filhos ponderada pelo peso do mês reproduz a variação do pai."""
    fato = _com_pai(fato)
    filhos = fato[fato.codigo_pai.notna()].assign(ponderado=lambda df: df.peso * df.variacao_mensal)
    agregado = (
        filhos.groupby(["mes", "tabela_sidra", "codigo_pai"], as_index=False)
        .agg(ponderado=("ponderado", "sum"), peso=("peso", "sum"))
        .rename(columns={"codigo_pai": "codigo_ibge"})
    )
    agregado["calculada"] = agregado.ponderado / agregado.peso
    agregado = agregado.merge(fato[["mes", "tabela_sidra", "codigo_ibge", "variacao_mensal"]])
    agregado["diferenca"] = agregado.calculada - agregado.variacao_mensal
    return _resultado("reconciliacao", agregado, TOLERANCIAS["reconciliacao"], excecoes)


def validar_continuidade(fato: pd.DataFrame, meses_por_tabela: dict[int, list[str]]) -> Resultado:
    """Toda categoria de cada tabela tem valor em todos os meses da tabela."""
    falhas = []
    verificados = 0
    for tabela, meses in meses_por_tabela.items():
        da_tabela = fato[fato.tabela_sidra == tabela]
        presentes = da_tabela.groupby("codigo_ibge").mes.nunique()
        verificados += len(presentes)
        for codigo, n in presentes[presentes != len(meses)].items():
            falhas.append({"tabela_sidra": tabela, "codigo_ibge": codigo, "meses": int(n)})
        faltando = sorted(set(meses) - set(da_tabela.mes))
        if faltando:
            falhas.append({"tabela_sidra": tabela, "meses_ausentes": faltando[:5]})
    return Resultado("continuidade", verificados, len(falhas), None, exemplos=falhas[:5])


def _acumulado_composto(serie: pd.Series, janela: int) -> pd.Series:
    fator = 1 + serie / 100
    return (fator.rolling(janela, min_periods=janela).apply(np.prod, raw=True) - 1) * 100


def validar_acumulados(fato: pd.DataFrame, excecoes: pd.DataFrame) -> list[Resultado]:
    """Acumulados no ano e em 12 meses, compondo as variações mensais dentro de cada tabela."""
    fato = fato.sort_values(["tabela_sidra", "codigo_sidra", "mes"]).copy()
    fato["ano"] = fato.mes.str[:4]
    fato["mes_do_ano"] = fato.mes.str[5:].astype(int)
    grupo = fato.groupby(["tabela_sidra", "codigo_sidra"], sort=False)

    # Acumulado no ano: só quando janeiro daquele ano está na mesma tabela.
    fato["fator"] = 1 + fato.variacao_mensal / 100
    fato["acum_ano_calc"] = (
        fato.groupby(["tabela_sidra", "codigo_sidra", "ano"]).fator.cumprod() - 1
    ) * 100
    primeiro_mes = fato.groupby(["tabela_sidra", "codigo_sidra", "ano"]).mes_do_ano.transform("min")
    ano = fato[primeiro_mes == 1].assign(
        diferenca=lambda df: df.acum_ano_calc - df.variacao_acum_ano
    )

    # Acumulado em 12 meses: janela inteira dentro da tabela, onde a 1120 foi publicada.
    fato["acum_12m_calc"] = grupo.variacao_mensal.transform(lambda s: _acumulado_composto(s, 12))
    doze = fato.assign(diferenca=lambda df: df.acum_12m_calc - df.variacao_acum_12m)
    return [
        _resultado("acumulado_ano", ano, TOLERANCIAS["acumulado_ano"], excecoes),
        _resultado("acumulado_12m", doze, TOLERANCIAS["acumulado_12m"], excecoes),
    ]


def serie_geral(fato: pd.DataFrame) -> pd.DataFrame:
    """Índice geral encadeado pelas tabelas de dados, um valor por mês."""
    geral = fato[fato.codigo_ibge == "0"].sort_values("mes")
    if geral.mes.duplicated().any():
        raise ValueError("mais de uma tabela de dados com o mesmo mês")
    return geral[["mes", "tabela_sidra", "variacao_mensal"]].reset_index(drop=True)


def validar_costura(
    fato: pd.DataFrame, referencia: pd.DataFrame, excecoes: pd.DataFrame
) -> list[Resultado]:
    """O índice geral das tabelas de dados reproduz a referência 3065."""
    geral = serie_geral(fato).merge(referencia, on="mes", suffixes=("", "_ref"))
    geral["codigo_ibge"] = "0"
    mensal = geral.assign(diferenca=geral.variacao_mensal - geral.variacao_mensal_ref)

    acumulados = []
    for janela, coluna in [
        (3, "variacao_acum_3m"),
        (6, "variacao_acum_6m"),
        (12, "variacao_acum_12m"),
    ]:
        calculado = _acumulado_composto(geral.variacao_mensal, janela)
        acumulados.append(
            geral[["mes", "tabela_sidra", "codigo_ibge"]].assign(
                diferenca=calculado - geral[coluna], janela=janela
            )
        )
    acumulados = pd.concat(acumulados, ignore_index=True)

    indice = geral.numero_indice.iloc[0] * (1 + geral.variacao_mensal / 100).cumprod()
    indice = indice / (1 + geral.variacao_mensal.iloc[0] / 100)
    numero = geral[["mes", "tabela_sidra", "codigo_ibge"]].assign(
        diferenca=(indice - geral.numero_indice) / geral.numero_indice
    )
    return [
        _resultado("costura_mensal", mensal, TOLERANCIAS["costura_mensal"], excecoes),
        _resultado("costura_acumulados", acumulados, TOLERANCIAS["costura_acumulados"], excecoes),
        _resultado(
            "costura_numero_indice",
            numero,
            TOLERANCIAS["costura_numero_indice_relativa"],
            excecoes,
        ),
    ]


def validar(
    fato: pd.DataFrame,
    referencia: pd.DataFrame,
    meses_por_tabela: dict[int, list[str]],
    excecoes: pd.DataFrame | None = None,
) -> list[Resultado]:
    excecoes = carregar_excecoes() if excecoes is None else excecoes
    return [
        validar_esquema(fato),
        *validar_pesos(fato, excecoes),
        validar_reconciliacao(fato, excecoes),
        validar_continuidade(fato, meses_por_tabela),
        *validar_acumulados(fato, excecoes),
        *validar_costura(fato, referencia, excecoes),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida o staging do IPCA-15.")
    parser.add_argument("--indice", default="ipca15")
    args = parser.parse_args(argv)

    indice = carregar_catalogo().indices[args.indice]
    pasta = diretorio_staging(indice)
    fato = pd.read_parquet(pasta / f"fato_{indice.codigo}.parquet")
    referencia = pd.read_parquet(pasta / f"ref_{indice.codigo}_geral.parquet")
    armazem = ArmazemRaw(indice.fonte)
    meses = {t.tabela: armazem.periodos(t.tabela) for t in indice.tabelas_dados}

    resultados = validar(fato, referencia, meses)
    for r in resultados:
        situacao = "ok " if r.ok else "FALHA"
        print(
            f"{situacao} {r.validacao:<24} verificados={r.verificados:<7} falhas={r.falhas:<5} "
            f"exceções={r.excecoes_aplicadas:<4} maior={r.maior_diferenca}"
        )
    (pasta / "validacao.json").write_text(
        json.dumps([asdict(r) | {"ok": r.ok} for r in resultados], ensure_ascii=False, indent=2)
    )
    return 0 if all(r.ok for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
