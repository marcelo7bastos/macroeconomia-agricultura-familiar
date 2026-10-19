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

# Arredondamento da fonte: variações com 2 casas (±0,005) e pesos com 4 casas (±0,00005).
# Os limites abaixo são o erro máximo que esse arredondamento pode produzir (A-014); passar
# deles é anomalia, não arredondamento. Ver METODOLOGIA.md, seção 6.
MEIA_CASA_VARIACAO = 0.005
MEIA_CASA_PESO = 0.00005

# A 356 das tabelas da POF 1995-96 e 2002-03 tem ruído acima do arredondamento (procedimento da
# fonte, A-016): limite por nível, no máximo observado na calibração da #5.
LIMITE_ACUMULADO_ANO_TABELAS_ANTIGAS = {
    "geral": 0.02,
    "grupo": 0.02,
    "subgrupo": 0.03,
    "item": 0.07,
    "subitem": 0.17,
}
TABELAS_ANTIGAS = {1646, 1387}
LIMITE_COSTURA_ACUMULADOS = {3: 0.01, 6: 0.01, "ano": 0.01, 12: 0.02}
LIMITE_INDICE_ENCADEADO_RELATIVO = 1e-4
VARIACAO_PLAUSIVEL = {"subitem": (-100.0, 300.0), "outros": (-50.0, 50.0)}


def _variacao_plausivel(df: pd.DataFrame) -> pd.Series:
    minimo = np.where(
        df.nivel_hierarquico == "subitem",
        *[VARIACAO_PLAUSIVEL[k][0] for k in ("subitem", "outros")],
    )
    maximo = np.where(
        df.nivel_hierarquico == "subitem",
        *[VARIACAO_PLAUSIVEL[k][1] for k in ("subitem", "outros")],
    )
    return df.variacao_mensal.between(minimo, maximo)


ESQUEMA_FATO = pa.DataFrameSchema(
    {
        "mes": pa.Column(str, pa.Check.str_matches(r"^\d{4}-(0[1-9]|1[0-2])$")),
        "versao_pof": pa.Column(str),
        "tabela_sidra": pa.Column(int),
        "codigo_sidra": pa.Column(int),
        "codigo_ibge": pa.Column(str),
        "nivel_hierarquico": pa.Column(str, pa.Check.isin(NIVEIS)),
        "variacao_mensal": pa.Column(float),
        "variacao_acum_ano": pa.Column(float),
        "variacao_acum_12m": pa.Column(float, nullable=True),
        "peso": pa.Column(float, pa.Check.in_range(0, 100)),
    },
    checks=[pa.Check(_variacao_plausivel, error="variação mensal fora da faixa plausível")],
    unique=["mes", "tabela_sidra", "codigo_sidra"],
    strict=True,
)


@dataclass
class Resultado:
    validacao: str
    verificados: int
    falhas: int
    limite: str
    excecoes_aplicadas: int = 0
    maior_diferenca: float | None = None
    exemplos: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.falhas == 0


def carregar_excecoes(caminho: Path = CAMINHO_EXCECOES) -> pd.DataFrame:
    excecoes = pd.read_csv(caminho, dtype=str)
    excecoes["tabela_sidra"] = excecoes["tabela_sidra"].astype(int)
    vazias = excecoes[excecoes[["justificativa", "aprendizado", "tipo"]].isna().any(axis=1)]
    if not vazias.empty:
        raise ValueError(
            f"exceção sem justificativa, tipo ou aprendizado: {vazias.values.tolist()}"
        )
    return excecoes.reset_index(drop=True)


class Validador:
    """Aplica as validações e as exceções documentadas, registrando quais exceções foram usadas."""

    def __init__(self, excecoes: pd.DataFrame) -> None:
        self.excecoes = excecoes
        self.usadas: set[int] = set()

    def resultado(self, nome: str, diferencas: pd.DataFrame, limite: str) -> Resultado:
        """`diferencas`: mes, tabela_sidra, codigo_ibge, diferenca e limite (por linha)."""
        diferencas = diferencas.dropna(subset=["diferenca"])
        fora = diferencas[diferencas.diferenca.abs() > diferencas.limite + 1e-9]
        coberto = pd.Series(False, index=fora.index)
        for posicao, excecao in self.excecoes[self.excecoes.validacao == nome].iterrows():
            casa = (
                (fora.tabela_sidra == excecao.tabela_sidra)
                & fora.codigo_ibge.str.fullmatch(excecao.codigo_ibge)
                & (fora.mes >= excecao.mes_inicio)
                & (fora.mes <= excecao.mes_fim)
            )
            if casa.any():
                self.usadas.add(posicao)
            coberto |= casa
        falhas = fora[~coberto]
        maior = diferencas.diferenca.abs().max() if not diferencas.empty else math.nan
        ordem = falhas.diferenca.abs().sort_values(ascending=False).index
        return Resultado(
            validacao=nome,
            verificados=len(diferencas),
            falhas=len(falhas),
            limite=limite,
            excecoes_aplicadas=int(coberto.sum()),
            maior_diferenca=None if math.isnan(maior) else round(float(maior), 6),
            exemplos=falhas.loc[ordem].head(5).round(6).to_dict("records"),
        )

    @property
    def excecoes_sem_uso(self) -> pd.DataFrame:
        """Exceções que não cobriram nenhuma falha: a fonte pode ter corrigido o dado."""
        return self.excecoes.drop(index=list(self.usadas))


def _codigo_pai(codigo: str) -> str | None:
    if codigo == "0":
        return None
    digitos = {1: 0, 2: 1, 4: 2, 7: 4}[len(codigo)]
    return "0" if digitos == 0 else codigo[:digitos]


def _com_pai(fato: pd.DataFrame) -> pd.DataFrame:
    return fato.assign(codigo_pai=fato.codigo_ibge.map(_codigo_pai))


def validar_esquema(fato: pd.DataFrame) -> Resultado:
    try:
        ESQUEMA_FATO.validate(fato, lazy=True)
    except pa.errors.SchemaErrors as erros:
        casos = erros.failure_cases
        return Resultado(
            "esquema", len(fato), len(casos), "contrato", exemplos=casos.head(5).to_dict("records")
        )
    return Resultado("esquema", len(fato), 0, "contrato")


def validar_pesos(fato: pd.DataFrame, validador: Validador) -> list[Resultado]:
    """Grupos somam 100, filhos somam o peso do pai e só há peso zero onde é esperado."""
    fato = _com_pai(fato)
    grupos = (
        fato[fato.nivel_hierarquico == "grupo"]
        .groupby(["mes", "tabela_sidra"], as_index=False)
        .agg(peso=("peso", "sum"), n=("peso", "size"))
        .assign(codigo_ibge="0")
    )
    grupos["diferenca"] = grupos.peso - 100
    grupos["limite"] = MEIA_CASA_PESO * (grupos.n + 1)

    soma = (
        fato[fato.codigo_pai.notna() & (fato.nivel_hierarquico != "grupo")]
        .groupby(["mes", "tabela_sidra", "codigo_pai"], as_index=False)
        .agg(soma_filhos=("peso", "sum"), n=("peso", "size"))
        .rename(columns={"codigo_pai": "codigo_ibge"})
    )
    filhos = soma.merge(fato[["mes", "tabela_sidra", "codigo_ibge", "peso"]], how="left")
    filhos["diferenca"] = filhos.soma_filhos - filhos.peso
    filhos["limite"] = MEIA_CASA_PESO * (filhos.n + 1)

    zeros = fato[["mes", "tabela_sidra", "codigo_ibge"]].assign(
        diferenca=(fato.peso == 0).astype(float), limite=0.0
    )
    return [
        validador.resultado("pesos_grupos", grupos, "0,00005 x (grupos + 1)"),
        validador.resultado("pesos_filhos", filhos, "0,00005 x (filhos + 1)"),
        validador.resultado("pesos_zero", zeros, "nenhum peso zero"),
    ]


def validar_reconciliacao(fato: pd.DataFrame, validador: Validador) -> Resultado:
    """Média dos filhos ponderada pelo peso do mês reproduz a variação do pai."""
    fato = _com_pai(fato)
    filhos = fato[fato.codigo_pai.notna()].assign(ponderado=lambda df: df.peso * df.variacao_mensal)
    chaves = ["mes", "tabela_sidra", "codigo_pai"]
    agregado = filhos.groupby(chaves, as_index=False).agg(
        ponderado=("ponderado", "sum"), soma_pesos=("peso", "sum")
    )
    agregado["calculada"] = agregado.ponderado / agregado.soma_pesos
    # Erro máximo do arredondamento dos pesos: soma de 0,00005 x |v_i - v| / soma dos pesos.
    filhos = filhos.merge(agregado[[*chaves, "calculada", "soma_pesos"]], on=chaves)
    filhos["erro_peso"] = MEIA_CASA_PESO * (filhos.variacao_mensal - filhos.calculada).abs()
    erro_peso = filhos.groupby(chaves, as_index=False).erro_peso.sum()
    agregado = agregado.merge(erro_peso, on=chaves).rename(columns={"codigo_pai": "codigo_ibge"})
    agregado = agregado.merge(fato[["mes", "tabela_sidra", "codigo_ibge", "variacao_mensal"]])
    agregado["diferenca"] = agregado.calculada - agregado.variacao_mensal
    agregado["limite"] = 2 * MEIA_CASA_VARIACAO + agregado.erro_peso / agregado.soma_pesos
    return validador.resultado(
        "reconciliacao",
        agregado,
        "0,005 (pai) + 0,005 (filhos) + soma(0,00005 x |v_i - v|) / soma(w)",
    )


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
    return Resultado(
        "continuidade", verificados, len(falhas), "todos os meses", exemplos=falhas[:5]
    )


def _acumulado_composto(serie: pd.Series, janela: int) -> pd.Series:
    fator = 1 + serie / 100
    return (fator.rolling(janela, min_periods=janela).apply(np.prod, raw=True) - 1) * 100


def _mes_seguinte(mes: pd.Series) -> pd.Series:
    ano, numero = mes.str[:4].astype(int), mes.str[5:].astype(int)
    return (ano + numero // 12).astype(str) + "-" + (numero % 12 + 1).map("{:02d}".format)


def validar_acumulados(fato: pd.DataFrame, validador: Validador) -> list[Resultado]:
    """Acumulado no ano (recursão de um passo) e em 12 meses (composição), dentro de cada tabela."""
    fato = fato.sort_values(["tabela_sidra", "codigo_sidra", "mes"]).reset_index(drop=True)
    anterior = fato[["tabela_sidra", "codigo_sidra", "mes", "variacao_acum_ano"]].assign(
        mes=lambda df: _mes_seguinte(df.mes)
    )
    anterior = anterior.rename(columns={"variacao_acum_ano": "acum_anterior"})
    ano = fato.merge(anterior, on=["tabela_sidra", "codigo_sidra", "mes"], how="left")
    janeiro = ano.mes.str[5:] == "01"
    ano["acum_anterior"] = ano.acum_anterior.where(~janeiro, 0.0)
    # Sem o mês anterior na mesma tabela (início de tabela fora de janeiro): não há como validar.
    ano = ano[ano.acum_anterior.notna()].copy()
    ano["calculada"] = ((1 + ano.acum_anterior / 100) * (1 + ano.variacao_mensal / 100) - 1) * 100
    ano["diferenca"] = ano.calculada - ano.variacao_acum_ano
    analitico = (
        MEIA_CASA_VARIACAO * (1 + ano.acum_anterior.abs() / 100)
        + MEIA_CASA_VARIACAO * (1 + ano.variacao_mensal.abs() / 100)
        + MEIA_CASA_VARIACAO
    )
    por_nivel = ano.nivel_hierarquico.map(LIMITE_ACUMULADO_ANO_TABELAS_ANTIGAS)
    ano["limite"] = np.where(
        ano.tabela_sidra.isin(TABELAS_ANTIGAS), np.maximum(analitico, por_nivel), analitico
    )

    # Composição vetorizada: soma móvel do log dos fatores, por categoria (fato já ordenado).
    doze = fato.copy()
    chave = ["tabela_sidra", "codigo_sidra"]
    fator = 1 + doze.variacao_mensal / 100
    doze["log_fator"], doze["inverso"] = np.log(fator), 1 / fator
    moveis = doze.groupby(chave, sort=False)[["log_fator", "inverso"]].rolling(12).sum()
    moveis = moveis.reset_index(level=chave, drop=True).sort_index()
    doze["calculada"] = (np.exp(moveis.log_fator) - 1) * 100
    soma_inversos = moveis.inverso
    doze["diferenca"] = doze.calculada - doze.variacao_acum_12m
    doze["limite"] = (
        MEIA_CASA_VARIACAO * (1 + doze.calculada.abs() / 100) * soma_inversos + MEIA_CASA_VARIACAO
    )
    return [
        validador.resultado(
            "acumulado_ano",
            ano,
            "arredondamento de um passo; 1646/1387: máximo por nível (ruído da fonte)",
        ),
        validador.resultado("acumulado_12m", doze, "arredondamento da composição de 12 meses"),
    ]


def serie_geral(fato: pd.DataFrame) -> pd.DataFrame:
    """Índice geral encadeado pelas tabelas de dados, um valor por mês."""
    geral = fato[fato.codigo_ibge == "0"].sort_values("mes")
    if geral.mes.duplicated().any():
        raise ValueError("mais de uma tabela de dados com o mesmo mês")
    return geral[["mes", "variacao_mensal"]].reset_index(drop=True)


def validar_costura(
    fato: pd.DataFrame, referencia: pd.DataFrame, validador: Validador
) -> list[Resultado]:
    """O índice geral das tabelas de dados reproduz a referência 3065."""
    geral = serie_geral(fato).merge(referencia, on="mes", suffixes=("", "_ref"))
    base = geral[["mes"]].assign(tabela_sidra=3065, codigo_ibge="0")

    mensal = base.assign(diferenca=geral.variacao_mensal - geral.variacao_mensal_ref, limite=0.0)

    acumulados = []
    for janela, coluna in [
        (3, "variacao_acum_3m"),
        (6, "variacao_acum_6m"),
        (12, "variacao_acum_12m"),
    ]:
        calculado = _acumulado_composto(geral.variacao_mensal, janela)
        acumulados.append(
            base.assign(
                diferenca=calculado - geral[coluna], limite=LIMITE_COSTURA_ACUMULADOS[janela]
            )
        )
    fator = 1 + geral.variacao_mensal / 100
    no_ano = (fator.groupby(geral.mes.str[:4]).cumprod() - 1) * 100
    tem_janeiro = geral.groupby(geral.mes.str[:4]).mes.transform("min").str[5:] == "01"
    acumulados.append(
        base.assign(
            diferenca=(no_ano - geral.variacao_acum_ano).where(tem_janeiro),
            limite=LIMITE_COSTURA_ACUMULADOS["ano"],
        )
    )
    acumulados = pd.concat(acumulados, ignore_index=True)

    um_passo = base.assign(
        diferenca=geral.numero_indice - geral.numero_indice.shift() * fator,
        limite=MEIA_CASA_PESO * geral.numero_indice + 2 * MEIA_CASA_VARIACAO,
    )
    encadeado = geral.numero_indice.iloc[0] * fator.cumprod() / fator.iloc[0]
    relativo = base.assign(
        diferenca=(encadeado - geral.numero_indice) / geral.numero_indice,
        limite=LIMITE_INDICE_ENCADEADO_RELATIVO,
    )
    return [
        validador.resultado("costura_mensal", mensal, "igualdade exata"),
        validador.resultado("costura_acumulados", acumulados, "0,01 (3, 6 meses e ano); 0,02 (12)"),
        validador.resultado("costura_numero_indice", um_passo, "0,00005·I + 0,01 por passo"),
        validador.resultado(
            "costura_numero_indice_encadeado", relativo, "desvio relativo de 0,01%"
        ),
    ]


def validar(
    fato: pd.DataFrame,
    referencia: pd.DataFrame,
    meses_por_tabela: dict[int, list[str]],
    excecoes: pd.DataFrame | None = None,
) -> tuple[list[Resultado], pd.DataFrame]:
    """Resultados de todas as validações e as exceções que não cobriram nenhuma falha."""
    validador = Validador(carregar_excecoes() if excecoes is None else excecoes)
    resultados = [
        validar_esquema(fato),
        *validar_pesos(fato, validador),
        validar_reconciliacao(fato, validador),
        validar_continuidade(fato, meses_por_tabela),
        *validar_acumulados(fato, validador),
        *validar_costura(fato, referencia, validador),
    ]
    return resultados, validador.excecoes_sem_uso


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

    resultados, sem_uso = validar(fato, referencia, meses)
    for r in resultados:
        situacao = "ok   " if r.ok else "FALHA"
        print(
            f"{situacao} {r.validacao:<32} verificados={r.verificados:<7} falhas={r.falhas:<5} "
            f"exceções={r.excecoes_aplicadas:<4} maior={r.maior_diferenca}"
        )
    for excecao in sem_uso.itertuples():
        print(
            f"aviso: exceção sem uso (a fonte corrigiu?): {excecao.validacao} "
            f"{excecao.tabela_sidra} {excecao.codigo_ibge} {excecao.mes_inicio}"
        )
    (pasta / "validacao.json").write_text(
        json.dumps(
            {
                "resultados": [asdict(r) | {"ok": r.ok} for r in resultados],
                "excecoes_sem_uso": sem_uso.to_dict("records"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(r.ok for r in resultados) and sem_uso.empty else 1


if __name__ == "__main__":
    sys.exit(main())
