"""Acumulados por janela (3, 6, 12, 24 e 36 meses e no ano), oficial primeiro (#42).

Para cada linha do índice encadeado e cada janela:

- **calculado:** `(I_t / I_(t-k) - 1) * 100` pelo índice da série longa; vazio se a janela sai do
  início da série (nunca atravessa quebra, decisão 0005);
- **oficial:** o que o IBGE publica para a mesma coisa: 1120 (12 meses) e 356 (no ano) da própria
  categoria; para o geral, 1118, 1119, 1120 e 356 da 3065 (tabela de referência).

O oficial é preferido quando mede o mesmo que a série longa:

- a janela cabe na série, ou começa antes do início dos dados (não há quebra, só falta de dado);
- no ano: a 356 só vale se o código de janeiro é o da linha (A-023). Série que começa no meio do
  ano ou cujo código mudou no ano fica sem o oficial, porque a 356 atravessaria a quebra;
- não é um valor que a fonte publicou errado (coluna `meses_com_erro_publicado` das exceções,
  A-015) e diverge do calculado acima do limite de arredondamento; aí vale o calculado.

`origem` diz de onde veio o valor. `cesta_variavel` marca a janela que contém mês com cesta
variável (A-013): o valor não reproduz um índice encadeado da categoria (METODOLOGIA 8.3).

Uso:

    uv run python -m macroaf.indicators.acumulados     # grava acumulados_ipca15 no staging
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from macroaf.catalogo import RAIZ, Indice, carregar_catalogo
from macroaf.indicators.indice import acumulado, acumulado_no_ano, caminho_indice
from macroaf.transform.harmonizacao import caminho_serie_longa
from macroaf.transform.ipca15 import diretorio_staging
from macroaf.validate.ipca15 import MEIA_CASA_VARIACAO, carregar_excecoes

# Janela → meses (None = desde janeiro).
JANELAS = {"3m": 3, "6m": 6, "12m": 12, "24m": 24, "36m": 36, "ano": None}
# Variável oficial por janela: da própria categoria e, para o geral, da tabela de referência.
OFICIAL_CATEGORIA = {"12m": "variacao_acum_12m", "ano": "variacao_acum_ano"}
OFICIAL_GERAL = {
    "3m": "variacao_acum_3m",
    "6m": "variacao_acum_6m",
    "12m": "variacao_acum_12m",
    "ano": "variacao_acum_ano",
}
# Validação cujas exceções A-015 apontam erro publicado naquela janela.
VALIDACAO_GERAL = {j: f"costura_acum_{j}" for j in OFICIAL_GERAL}
VALIDACAO_CATEGORIA = {"ano": "acumulado_ano", "12m": "acumulado_12m"}
INICIO_DOS_DADOS = "inicio dos dados"
COLUNAS = [
    "serie_id",
    "mes",
    "tabela_sidra",
    "codigo_sidra",
    "codigo_ibge",
    "nivel_hierarquico",
    "janela",
    "acumulado",
    "origem",
    "cesta_variavel",
]


def tamanho_da_janela(dados: pd.DataFrame, janela: str) -> pd.Series:
    meses = JANELAS[janela]
    if meses is None:
        return dados.mes.str[5:].astype(int)
    return pd.Series(meses, index=dados.index)


def limite_acumulado(dados: pd.DataFrame, calculado: pd.Series, tamanho: pd.Series) -> pd.Series:
    """Erro máximo de um acumulado composto de variações com 2 casas (A-014), por linha."""
    inverso = (1 / (1 + dados.variacao_mensal / 100)).groupby(dados.serie_id).cumsum()
    soma = pd.Series(np.nan, index=dados.index)
    for k in sorted(tamanho.unique()):
        linhas = tamanho == k
        anterior = inverso.groupby(dados.serie_id).shift(int(k)).fillna(0)
        soma[linhas] = (inverso - anterior)[linhas]
    return MEIA_CASA_VARIACAO * (1 + calculado.abs() / 100) * soma + MEIA_CASA_VARIACAO


def _erro_publicado(dados: pd.DataFrame, excecoes: pd.DataFrame, validacao, tabela) -> pd.Series:
    """Linhas cujo valor publicado está errado (A-015): o mês do erro, não o escopo da exceção."""
    erro = pd.Series(False, index=dados.index)
    for e in excecoes[excecoes.validacao == validacao].itertuples():
        erro |= (
            (tabela == e.tabela_sidra)
            & dados.codigo_ibge.str.fullmatch(e.codigo_ibge)
            & dados.mes.isin(e.meses_com_erro_publicado)
        )
    return erro


def _cesta_na_janela(dados: pd.DataFrame, janela: str) -> pd.Series:
    marca = dados.cesta_variavel.astype(int)
    if JANELAS[janela] is None:
        grupo = [dados.serie_id, dados.mes.str[:4]]
        return marca.groupby(grupo).cummax().astype(bool)
    moveis = marca.groupby(dados.serie_id).rolling(JANELAS[janela], min_periods=1).max()
    return moveis.reset_index(level=0, drop=True).sort_index().astype(bool)


def montar_acumulados(
    indice: pd.DataFrame,
    longa: pd.DataFrame,
    referencia: pd.DataFrame,
    excecoes: pd.DataFrame,
    tabela_referencia: int,
) -> pd.DataFrame:
    """Uma linha por série, mês e janela: o oficial onde mede o mesmo; senão, o calculado."""
    publicados = longa[["serie_id", "mes", *OFICIAL_CATEGORIA.values(), "entrada"]]
    dados = indice.merge(publicados, on=["serie_id", "mes"], how="left", validate="one_to_one")
    # As janelas por deslocamento e o limite supõem linhas ordenadas por série e mês.
    if not dados[["serie_id", "mes"]].equals(
        dados[["serie_id", "mes"]].sort_values(["serie_id", "mes"], ignore_index=True)
    ):
        raise ValueError("índice fora da ordem por série e mês")
    geral = dados.codigo_ibge == "0"
    posicao = dados.groupby("serie_id").cumcount()
    antes_dos_dados = dados.entrada == INICIO_DOS_DADOS
    ano = [dados.serie_id, dados.mes.str[:4]]
    mesmo_codigo_no_ano = dados.groupby(ano).codigo_ibge.transform("first") == dados.codigo_ibge
    referencia = referencia.set_index("mes")

    partes = []
    for janela, meses in JANELAS.items():
        tamanho = tamanho_da_janela(dados, janela)
        calculado = acumulado_no_ano(dados) if meses is None else acumulado(dados, meses)
        cabe = posicao >= tamanho - 1
        oficial = pd.Series(np.nan, index=dados.index)
        if janela in OFICIAL_CATEGORIA:
            oficial = dados[OFICIAL_CATEGORIA[janela]].where(~geral)
        if janela in OFICIAL_GERAL:
            oficial = oficial.where(~geral, dados.mes.map(referencia[OFICIAL_GERAL[janela]]))
        valido = oficial.notna() & (cabe | antes_dos_dados)
        if meses is None:
            valido &= mesmo_codigo_no_ano
        erro_publicado = _erro_publicado(
            dados, excecoes, VALIDACAO_GERAL.get(janela), tabela_referencia
        ).where(geral, False) | _erro_publicado(
            dados, excecoes, VALIDACAO_CATEGORIA.get(janela), dados.tabela_sidra
        ).where(~geral, False)
        diverge = (oficial - calculado).abs() > limite_acumulado(dados, calculado, tamanho)
        valido &= ~(erro_publicado & (diverge | calculado.isna()))
        parte = dados.assign(
            janela=janela,
            acumulado=oficial.where(valido, calculado),
            origem=np.where(valido, "oficial", np.where(calculado.notna(), "calculado", None)),
            cesta_variavel=_cesta_na_janela(dados, janela),
        )
        partes.append(parte[parte.acumulado.notna()])
    return pd.concat(partes, ignore_index=True)[COLUNAS]


def caminho_acumulados(indice: Indice) -> Path:
    return diretorio_staging(indice) / f"acumulados_{indice.codigo}.parquet"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calcula os acumulados por janela.")
    parser.add_argument("--indice", default="ipca15")
    args = parser.parse_args(argv)

    catalogo_indice = carregar_catalogo().indices[args.indice]
    referencia_tabela = next(t.tabela for t in catalogo_indice.tabelas if t.papel == "referencia")
    pasta = diretorio_staging(catalogo_indice)
    resultado = montar_acumulados(
        pd.read_parquet(caminho_indice(catalogo_indice)),
        pd.read_parquet(caminho_serie_longa(catalogo_indice)),
        pd.read_parquet(pasta / f"ref_{catalogo_indice.codigo}_geral.parquet"),
        carregar_excecoes(catalogo_indice),
        referencia_tabela,
    )
    destino = caminho_acumulados(catalogo_indice)
    resultado.to_parquet(destino, index=False)
    contagem = resultado.groupby(["janela", "origem"]).size().unstack(fill_value=0)
    print(contagem.reindex(list(JANELAS)).to_string())
    print(f"{len(resultado)} linhas em {destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
