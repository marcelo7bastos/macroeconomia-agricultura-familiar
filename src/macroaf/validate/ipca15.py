"""Validações do IPCA-15 (seção 4.4 do planejamento; regras e limites em METODOLOGIA.md, seção 6).

Cada validação devolve um `Resultado`; uma falha bloqueia a publicação. O que varia por índice
fica fora do código:

- `reference/excecoes_validacao_<indice>.csv`: diferenças conhecidas e explicadas, cada uma com
  escopo (validação, tabela, padrão de código, meses), tipo, justificativa, A-NNN e o número
  exato de falhas que cobre (sentinela);
- `reference/limites_validacao_<indice>.csv`: limites empíricos por tabela e nível, onde a fonte
  tem ruído acima do arredondamento;
- `config/series.yaml`: tabelas de dados, tabela de referência e períodos esperados.

Uso:

    uv run python -m macroaf.validate.ipca15     # valida o staging e grava validacao.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
import pandera.pandas as pa

from macroaf.catalogo import RAIZ, Indice, carregar_catalogo
from macroaf.extract.atualizar import meses_entre
from macroaf.extract.raw import ArmazemRaw
from macroaf.transform.classificacao import NIVEIS
from macroaf.transform.ipca15 import diretorio_staging

# Arredondamento da fonte: variações e número-índice com 2 casas (±0,005) e pesos com 4 casas
# (±0,00005). Os limites analíticos são o erro máximo que esse arredondamento pode produzir
# (A-014); passar deles é anomalia, não arredondamento.
MEIA_CASA_VARIACAO = 0.005
MEIA_CASA_PESO = 0.00005
LIMITE_INDICE_ENCADEADO_RELATIVO = 1e-4
VARIACAO_PLAUSIVEL = {"subitem": (-100.0, 300.0), "outros": (-50.0, 50.0)}
PADRAO_POR_NIVEL = {
    "geral": r"0",
    "grupo": r"\d",
    "subgrupo": r"\d{2}",
    "item": r"\d{4}",
    "subitem": r"\d{7}",
}


def _variacao_plausivel(df: pd.DataFrame) -> pd.Series:
    subitem = df.nivel_hierarquico == "subitem"
    minimo = np.where(subitem, VARIACAO_PLAUSIVEL["subitem"][0], VARIACAO_PLAUSIVEL["outros"][0])
    maximo = np.where(subitem, VARIACAO_PLAUSIVEL["subitem"][1], VARIACAO_PLAUSIVEL["outros"][1])
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
    ausentes: int = 0
    maior_diferenca: float | None = None
    exemplos: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.falhas == 0


@dataclass
class Configuracao:
    """O que as validações precisam saber do índice, vindo do catálogo, do raw e de `reference/`."""

    excecoes: pd.DataFrame
    limites: pd.DataFrame
    tabela_referencia: int
    meses_esperados: dict[int, list[str]]
    categorias_esperadas: dict[int, set[int]]


def _ler_csv_documentado(caminho, obrigatorias: list[str]) -> pd.DataFrame:
    tabela = pd.read_csv(caminho, dtype=str)
    tabela["tabela_sidra"] = tabela["tabela_sidra"].astype(int)
    incompletas = tabela[tabela[obrigatorias].isna().any(axis=1)]
    if not incompletas.empty:
        raise ValueError(
            f"{caminho.name}: linhas sem {obrigatorias}: {incompletas.values.tolist()}"
        )
    if not tabela.aprendizado.str.fullmatch(r"A-\d{3}").all():
        raise ValueError(f"{caminho.name}: aprendizado fora do formato A-NNN")
    return tabela.reset_index(drop=True)


def carregar_excecoes(indice: Indice) -> pd.DataFrame:
    caminho = RAIZ / "reference" / f"excecoes_validacao_{indice.codigo}.csv"
    excecoes = _ler_csv_documentado(
        caminho, ["validacao", "tipo", "justificativa", "aprendizado", "falhas_cobertas"]
    )
    excecoes["falhas_cobertas"] = excecoes.falhas_cobertas.astype(int)
    if not set(excecoes.tipo) <= {"estrutural", "fonte"}:
        raise ValueError(f"{caminho.name}: tipo deve ser estrutural ou fonte")
    return excecoes


def carregar_limites(indice: Indice) -> pd.DataFrame:
    caminho = RAIZ / "reference" / f"limites_validacao_{indice.codigo}.csv"
    limites = _ler_csv_documentado(caminho, ["validacao", "nivel_hierarquico", "limite"])
    limites["limite"] = limites.limite.astype(float)
    return limites


def carregar_configuracao(indice: Indice, armazem: ArmazemRaw, dim: pd.DataFrame) -> Configuracao:
    """Meses esperados vêm do catálogo; o fim de tabela aberta é o último mês no raw do índice."""
    ultimo = max(max(armazem.periodos(t.tabela), default=t.inicio) for t in indice.tabelas)
    meses = {t.tabela: meses_entre(t.inicio, t.fim or ultimo) for t in indice.tabelas_dados}
    categorias = {tabela: set(grupo.codigo_sidra) for tabela, grupo in dim.groupby("tabela_sidra")}
    return Configuracao(
        excecoes=carregar_excecoes(indice),
        limites=carregar_limites(indice),
        tabela_referencia=indice.tabelas_referencia[0].tabela,
        meses_esperados=meses,
        categorias_esperadas=categorias,
    )


class Validador:
    """Aplica limites e exceções, contando quantas falhas cada exceção cobriu."""

    def __init__(self, excecoes: pd.DataFrame) -> None:
        self.excecoes = excecoes
        self.cobertas = pd.Series(0, index=excecoes.index, dtype=int)

    def resultado(
        self, nome: str, diferencas: pd.DataFrame, limite: str, permitir_ausente: bool = False
    ) -> Resultado:
        """`diferencas`: mes, tabela_sidra, codigo_ibge, diferenca e limite (por linha).

        Diferença ausente é falha, salvo quando a regra não se aplica àquela linha
        (`permitir_ausente`, ex.: acumulado em 12 meses não publicado).
        """
        ausentes = diferencas[diferencas.diferenca.isna()]
        presentes = diferencas.dropna(subset=["diferenca"])
        fora = presentes[presentes.diferenca.abs() > presentes.limite + 1e-9]
        coberto = pd.Series(False, index=fora.index)
        # Cada falha é atribuída à primeira exceção que a cobre, na ordem do CSV.
        for posicao, excecao in self.excecoes[self.excecoes.validacao == nome].iterrows():
            casa = (
                ~coberto
                & (fora.tabela_sidra == excecao.tabela_sidra)
                & fora.codigo_ibge.str.fullmatch(excecao.codigo_ibge)
                & (fora.mes >= excecao.mes_inicio)
                & (fora.mes <= excecao.mes_fim)
            )
            self.cobertas[posicao] += int(casa.sum())
            coberto |= casa
        falhas = fora[~coberto]
        n_ausentes = 0 if permitir_ausente else len(ausentes)
        maior = presentes.diferenca.abs().max() if not presentes.empty else math.nan
        ordem = falhas.diferenca.abs().sort_values(ascending=False).index
        exemplos = falhas.loc[ordem].head(5).round(6).to_dict("records")
        if n_ausentes:
            exemplos += ausentes.head(5 - len(exemplos)).round(6).to_dict("records")
        return Resultado(
            validacao=nome,
            verificados=len(presentes),
            falhas=len(falhas) + n_ausentes,
            limite=limite,
            excecoes_aplicadas=int(coberto.sum()),
            ausentes=len(ausentes),
            maior_diferenca=None if math.isnan(maior) else round(float(maior), 6),
            exemplos=exemplos,
        )

    @property
    def sentinelas(self) -> pd.DataFrame:
        """Exceções que cobriram um número de falhas diferente do registrado no CSV.

        Menos que o registrado: a fonte pode ter corrigido o dado. Mais: há erro novo dentro do
        escopo da exceção. Nos dois casos a exceção precisa ser revista.
        """
        divergentes = self.excecoes.assign(obtidas=self.cobertas)
        return divergentes[divergentes.obtidas != divergentes.falhas_cobertas]


def _codigo_pai(codigo: str) -> str | None:
    if codigo == "0":
        return None
    digitos = {1: 0, 2: 1, 4: 2, 7: 4}[len(codigo)]
    return "0" if digitos == 0 else codigo[:digitos]


def _com_pai(fato: pd.DataFrame) -> pd.DataFrame:
    return fato.assign(codigo_pai=fato.codigo_ibge.map(_codigo_pai))


def _fator(variacao: pd.Series) -> pd.Series:
    """1 + v/100, com fator não positivo (variação de -100% ou menos) tratado como ausente."""
    fator = 1 + variacao / 100
    return fator.where(fator > 0)


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
    # Pai ausente vira diferença ausente, contada como falha.
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
    agregado = agregado.merge(
        fato[["mes", "tabela_sidra", "codigo_ibge", "variacao_mensal"]], how="left"
    )
    agregado["diferenca"] = agregado.calculada - agregado.variacao_mensal
    agregado["limite"] = 2 * MEIA_CASA_VARIACAO + agregado.erro_peso / agregado.soma_pesos
    return validador.resultado(
        "reconciliacao",
        agregado,
        "0,005 (pai) + 0,005 (filhos) + soma(0,00005 x |v_i - v|) / soma(w)",
    )


def validar_continuidade(fato: pd.DataFrame, configuracao: Configuracao) -> Resultado:
    """Toda categoria esperada (dim) tem valor em todo mês esperado (catálogo), e só neles."""
    falhas, exemplos, verificados = 0, [], 0
    for tabela, meses in configuracao.meses_esperados.items():
        esperado = pd.MultiIndex.from_product(
            [meses, sorted(configuracao.categorias_esperadas.get(tabela, set()))],
            names=["mes", "codigo_sidra"],
        )
        obtido = pd.MultiIndex.from_frame(
            fato.loc[fato.tabela_sidra == tabela, ["mes", "codigo_sidra"]]
        )
        verificados += len(esperado)
        for caso, diferenca in [
            ("ausente", esperado.difference(obtido)),
            ("fora do período ou da classificação", obtido.difference(esperado)),
        ]:
            falhas += len(diferenca)
            exemplos += [
                {"tabela_sidra": tabela, "mes": mes, "codigo_sidra": codigo, "caso": caso}
                for mes, codigo in diferenca[:5]
            ]
    return Resultado(
        "continuidade", verificados, falhas, "catálogo x dim_classificacao", exemplos=exemplos[:5]
    )


def _mes_seguinte(mes: pd.Series) -> pd.Series:
    ano, numero = mes.str[:4].astype(int), mes.str[5:].astype(int)
    return (ano + numero // 12).astype(str) + "-" + (numero % 12 + 1).map("{:02d}".format)


def _limite_composicao(acumulado: pd.Series, soma_inversos: pd.Series) -> pd.Series:
    """Erro máximo de um acumulado composto de variações com 2 casas: ∂A/∂v_j = (1+A)/(1+v_j)."""
    return MEIA_CASA_VARIACAO * (1 + acumulado.abs() / 100) * soma_inversos + MEIA_CASA_VARIACAO


def _composicao_movel(
    df: pd.DataFrame, chave: list[str], janela: int
) -> tuple[pd.Series, pd.Series]:
    """Acumulado composto em janela móvel e soma dos inversos dos fatores (df ordenado)."""
    fator = _fator(df.variacao_mensal)
    auxiliar = pd.DataFrame({"log": np.log(fator), "inverso": 1 / fator}, index=df.index)
    auxiliar[chave] = df[chave]
    moveis = auxiliar.groupby(chave, sort=False)[["log", "inverso"]].rolling(janela).sum()
    moveis = moveis.reset_index(level=chave, drop=True).sort_index()
    return (np.exp(moveis["log"]) - 1) * 100, moveis["inverso"]


def _limite_por_nivel(dados: pd.DataFrame, limites: pd.DataFrame, validacao: str) -> pd.Series:
    """Limite empírico por tabela e nível, onde configurado (NaN onde não há)."""
    da_validacao = limites[limites.validacao == validacao][
        ["tabela_sidra", "nivel_hierarquico", "limite"]
    ]
    return (
        dados[["tabela_sidra", "nivel_hierarquico"]].merge(da_validacao, how="left").limite.values
    )


def validar_acumulados(
    fato: pd.DataFrame, validador: Validador, limites: pd.DataFrame
) -> list[Resultado]:
    """Acumulado no ano (um passo) e em 12 meses (composição), dentro de cada tabela."""
    fato = fato.sort_values(["tabela_sidra", "codigo_sidra", "mes"]).reset_index(drop=True)
    anterior = fato[["tabela_sidra", "codigo_sidra", "mes", "variacao_acum_ano"]].assign(
        mes=lambda df: _mes_seguinte(df.mes)
    )
    anterior = anterior.rename(columns={"variacao_acum_ano": "acum_anterior"})
    ano = fato.merge(anterior, on=["tabela_sidra", "codigo_sidra", "mes"], how="left")
    janeiro = ano.mes.str[5:] == "01"
    ano["acum_anterior"] = ano.acum_anterior.where(~janeiro, 0.0)
    # Sem o mês anterior na mesma tabela (início de tabela fora de janeiro): a regra não se aplica.
    ano = ano[ano.acum_anterior.notna()].reset_index(drop=True)
    janeiro = ano.mes.str[5:] == "01"
    ano["calculada"] = ((1 + ano.acum_anterior / 100) * _fator(ano.variacao_mensal) - 1) * 100
    ano["diferenca"] = ano.calculada - ano.variacao_acum_ano
    analitico = (
        MEIA_CASA_VARIACAO * (1 + ano.acum_anterior.abs() / 100)
        + MEIA_CASA_VARIACAO * (1 + ano.variacao_mensal.abs() / 100)
        + MEIA_CASA_VARIACAO
    )
    empirico = _limite_por_nivel(ano, limites, "acumulado_ano")
    limite = np.fmax(analitico, empirico)
    # Em janeiro o acumulado no ano é a própria variação: igualdade exata no SIDRA.
    ano["limite"] = np.where(janeiro, 0.0, limite)

    doze = fato.copy()
    doze["calculada"], soma_inversos = _composicao_movel(doze, ["tabela_sidra", "codigo_sidra"], 12)
    doze["diferenca"] = doze.calculada - doze.variacao_acum_12m
    doze["limite"] = _limite_composicao(doze.calculada, soma_inversos)
    return [
        validador.resultado(
            "acumulado_ano",
            ano,
            "janeiro: igualdade; demais: arredondamento de um passo ou limite por nível",
        ),
        validador.resultado(
            "acumulado_12m", doze, "arredondamento da composição de 12 meses", permitir_ausente=True
        ),
    ]


def serie_geral(fato: pd.DataFrame) -> pd.DataFrame:
    """Índice geral encadeado pelas tabelas de dados, um valor por mês."""
    geral = fato[fato.codigo_ibge == "0"].sort_values("mes")
    if geral.mes.duplicated().any():
        raise ValueError("mais de uma tabela de dados com o mesmo mês")
    return geral[["mes", "variacao_mensal"]].reset_index(drop=True)


def validar_costura(
    fato: pd.DataFrame, referencia: pd.DataFrame, validador: Validador, tabela_referencia: int
) -> list[Resultado]:
    """O índice geral das tabelas de dados reproduz a tabela de referência."""
    geral = serie_geral(fato).merge(referencia, on="mes", how="outer", suffixes=("", "_ref"))
    base = geral[["mes"]].assign(tabela_sidra=tabela_referencia, codigo_ibge="0", chave=0)
    fator = _fator(geral.variacao_mensal)
    resultados = [
        validador.resultado(
            "costura_mensal",
            base.assign(diferenca=geral.variacao_mensal - geral.variacao_mensal_ref, limite=0.0),
            "igualdade exata",
        )
    ]

    serie = geral.assign(chave=0)
    for janela, coluna in [
        (3, "variacao_acum_3m"),
        (6, "variacao_acum_6m"),
        (12, "variacao_acum_12m"),
    ]:
        calculado, inversos = _composicao_movel(serie, ["chave"], janela)
        resultados.append(
            validador.resultado(
                f"costura_acum_{janela}m",
                base.assign(
                    diferenca=calculado - geral[coluna],
                    limite=_limite_composicao(calculado, inversos),
                ),
                f"arredondamento da composição de {janela} meses",
                permitir_ausente=True,
            )
        )
    ano = geral.mes.str[:4]
    no_ano = (fator.groupby(ano).cumprod() - 1) * 100
    inversos_ano = (1 / fator).groupby(ano).cumsum()
    tem_janeiro = geral.groupby(ano).mes.transform("min").str[5:] == "01"
    resultados.append(
        validador.resultado(
            "costura_acum_ano",
            base.assign(
                diferenca=(no_ano - geral.variacao_acum_ano).where(tem_janeiro),
                limite=_limite_composicao(no_ano, inversos_ano),
            ),
            "arredondamento da composição desde janeiro",
            permitir_ausente=True,
        )
    )

    passo = geral.numero_indice.shift() * fator
    resultados.append(
        validador.resultado(
            "costura_numero_indice",
            base.assign(
                diferenca=geral.numero_indice - passo,
                limite=MEIA_CASA_VARIACAO / 100 * geral.numero_indice + 2 * MEIA_CASA_VARIACAO,
            ).iloc[1:],
            "0,00005 x I + 0,01 por passo",
        )
    )
    encadeado = geral.numero_indice.iloc[0] * fator.cumprod() / fator.iloc[0]
    resultados.append(
        validador.resultado(
            "costura_numero_indice_encadeado",
            base.assign(
                diferenca=(encadeado - geral.numero_indice) / geral.numero_indice,
                limite=LIMITE_INDICE_ENCADEADO_RELATIVO,
            ),
            "desvio relativo de 0,01%",
        )
    )
    return resultados


def validar(
    fato: pd.DataFrame, referencia: pd.DataFrame, configuracao: Configuracao
) -> tuple[list[Resultado], pd.DataFrame]:
    """Resultados de todas as validações e as exceções cuja contagem não bate (sentinelas)."""
    validador = Validador(configuracao.excecoes)
    resultados = [
        validar_esquema(fato),
        *validar_pesos(fato, validador),
        validar_reconciliacao(fato, validador),
        validar_continuidade(fato, configuracao),
        *validar_acumulados(fato, validador, configuracao.limites),
        *validar_costura(fato, referencia, validador, configuracao.tabela_referencia),
    ]
    return resultados, validador.sentinelas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida o staging de um índice.")
    parser.add_argument("--indice", default="ipca15")
    args = parser.parse_args(argv)

    indice = carregar_catalogo().indices[args.indice]
    pasta = diretorio_staging(indice)
    fato = pd.read_parquet(pasta / f"fato_{indice.codigo}.parquet")
    referencia = pd.read_parquet(pasta / f"ref_{indice.codigo}_geral.parquet")
    dim = pd.read_parquet(pasta / "dim_classificacao.parquet")
    configuracao = carregar_configuracao(indice, ArmazemRaw(indice.fonte), dim)

    resultados, sentinelas = validar(fato, referencia, configuracao)
    for r in resultados:
        situacao = "ok   " if r.ok else "FALHA"
        print(
            f"{situacao} {r.validacao:<32} verificados={r.verificados:<7} falhas={r.falhas:<5} "
            f"exceções={r.excecoes_aplicadas:<5} maior={r.maior_diferenca}"
        )
    for s in sentinelas.itertuples():
        print(
            f"SENTINELA {s.validacao} {s.tabela_sidra} {s.codigo_ibge} "
            f"{s.mes_inicio}..{s.mes_fim}: "
            f"registradas {s.falhas_cobertas}, obtidas {s.obtidas}"
        )
    (pasta / "validacao.json").write_text(
        json.dumps(
            {
                "resultados": [asdict(r) | {"ok": r.ok} for r in resultados],
                "sentinelas": sentinelas.to_dict("records"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(r.ok for r in resultados) and sentinelas.empty else 1


if __name__ == "__main__":
    sys.exit(main())
