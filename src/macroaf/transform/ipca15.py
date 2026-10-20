"""`fato_ipca15` e `ref_ipca15_geral`: valores do raw em formato tidy, ligados à classificação.

- `fato_ipca15`: uma linha por mês e categoria das tabelas de dados (1646, 1387, 1705, 7062), com
  as variáveis em colunas. A ligação com a `dim_classificacao` é por `(tabela_sidra, codigo_sidra)`;
  o código IBGE sozinho não identifica a categoria entre POFs (A-012, METODOLOGIA.md).
- `ref_ipca15_geral`: a tabela de referência 3065 (só índice geral), usada nas validações.

Valores: `...` (não disponível) vira ausente, nunca zero; qualquer outro texto não numérico
interrompe a transformação, para ser examinado antes de ganhar um tratamento (A-009).

Uso:

    uv run python -m macroaf.transform.ipca15     # grava o staging do IPCA-15
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

from macroaf.catalogo import RAIZ, Indice, Tabela, carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.transform.classificacao import montar_dim_classificacao

AUSENTE = "..."
COLUNAS_FATO = [
    "mes",
    "versao_pof",
    "tabela_sidra",
    "codigo_sidra",
    "codigo_ibge",
    "nivel_hierarquico",
    "variacao_mensal",
    "variacao_acum_ano",
    "variacao_acum_12m",
    "peso",
]
COLUNAS_REFERENCIA = [
    "mes",
    "numero_indice",
    "variacao_mensal",
    "variacao_acum_3m",
    "variacao_acum_6m",
    "variacao_acum_ano",
    "variacao_acum_12m",
]


class ErroTransformacao(ValueError):
    """O raw tem algo que a transformação não sabe tratar."""


def converter_valor(texto: str, contexto: str) -> float:
    """Valor do SIDRA (texto com ponto decimal) em número; `...` vira NaN."""
    if texto == "-":
        return 0.0  # SIDRA: zero absoluto (https://apisidra.ibge.gov.br/home/ajuda).
    if texto == AUSENTE:
        return math.nan
    try:
        return float(texto)
    except ValueError:
        raise ErroTransformacao(f"{contexto}: valor não numérico {texto!r}") from None


def _registros_da_tabela(armazem: ArmazemRaw, tabela: Tabela, nomes: dict[int, str]) -> list:
    linhas = []
    for periodo in armazem.periodos(tabela.tabela):
        arquivo = armazem.vigente(tabela.tabela, periodo)
        dados = json.loads(armazem.ler(arquivo))
        for registro in dados[1:]:
            contexto = f"{arquivo.name}, variável {registro['D2C']}"
            linhas.append(
                {
                    "mes": periodo,
                    "tabela_sidra": tabela.tabela,
                    "codigo_sidra": int(registro["D4C"]) if "D4C" in registro else None,
                    "variavel": nomes[int(registro["D2C"])],
                    "valor": converter_valor(registro["V"], contexto),
                }
            )
    return linhas


def _nomes_variaveis(indice: Indice) -> dict[int, str]:
    return {codigo: variavel.nome for codigo, variavel in indice.variaveis.items()}


def montar_fato(
    indice: Indice,
    armazem: ArmazemRaw,
    dim: pd.DataFrame | None = None,
    *,
    incluir_indisponiveis: bool = False,
) -> pd.DataFrame:
    """Valores das tabelas de dados, uma linha por mês e categoria."""
    dim = montar_dim_classificacao(indice, armazem) if dim is None else dim
    nomes = _nomes_variaveis(indice)
    longo = pd.DataFrame(
        [
            linha
            for tabela in indice.tabelas_dados
            for linha in _registros_da_tabela(armazem, tabela, nomes)
        ]
    )
    # `pivot` (e não `pivot_table`) falha se houver registro repetido e preserva os NaN.
    largo = longo.pivot(
        index=["mes", "tabela_sidra", "codigo_sidra"], columns="variavel", values="valor"
    ).reset_index()
    largo.columns.name = None
    for coluna in ["variacao_mensal", "variacao_acum_ano", "variacao_acum_12m", "peso"]:
        if coluna not in largo:
            largo[coluna] = math.nan

    chaves = dim[["tabela_sidra", "codigo_sidra", "versao_pof", "codigo_ibge", "nivel_hierarquico"]]
    fato = largo.merge(chaves, on=["tabela_sidra", "codigo_sidra"], how="left", validate="m:1")
    sem_classificacao = fato[fato.codigo_ibge.isna()]
    if not sem_classificacao.empty:
        exemplos = sem_classificacao[["tabela_sidra", "codigo_sidra"]].drop_duplicates().head()
        raise ErroTransformacao(f"valores sem categoria na dim_classificacao: {exemplos.values}")
    # Categorias sem coleta têm todas as medidas fundamentais ausentes no raw.
    # Preservar essas respostas na auditoria, sem fabricar observações no fato.
    if not incluir_indisponiveis:
        sem_coleta = fato[["variacao_mensal", "variacao_acum_ano", "peso"]].isna().all(axis=1)
        fato = fato[~sem_coleta]
    # Tabelas sem a variável 1120 (1646, 1387) aparecem com a coluna ausente: fica NaN.
    return (
        fato[COLUNAS_FATO]
        .sort_values(["mes", "tabela_sidra", "codigo_ibge"])
        .reset_index(drop=True)
    )


def montar_referencia(indice: Indice, armazem: ArmazemRaw) -> pd.DataFrame:
    """Tabela(s) de referência do índice geral, uma linha por mês."""
    nomes = _nomes_variaveis(indice)
    linhas = [
        linha
        for tabela in indice.tabelas_referencia
        for linha in _registros_da_tabela(armazem, tabela, nomes)
    ]
    largo = pd.DataFrame(linhas).pivot(index="mes", columns="variavel", values="valor")
    largo.columns.name = None
    referencia = largo.reset_index()[COLUNAS_REFERENCIA]
    # O raw preserva toda a referência; o staging acompanha a cobertura do detalhe.
    inicio = min(t.inicio for t in indice.tabelas_dados)
    fim = indice.tabelas_dados[-1].fim
    recorte = referencia.mes >= inicio
    if fim is not None:
        recorte &= referencia.mes <= fim
    return referencia[recorte].reset_index(drop=True)


def diretorio_staging(indice: Indice) -> Path:
    return RAIZ / "data" / "staging" / indice.codigo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monta fato e referência a partir do raw.")
    parser.add_argument("--indice", default="ipca15")
    args = parser.parse_args(argv)

    indice = carregar_catalogo().indices[args.indice]
    armazem = ArmazemRaw(indice.fonte)
    try:
        dim = montar_dim_classificacao(indice, armazem)
        fato = montar_fato(indice, armazem, dim)
        referencia = montar_referencia(indice, armazem)
    except ErroTransformacao as erro:
        print(f"erro na transformação: {erro}", file=sys.stderr)
        return 1
    destino = diretorio_staging(indice)
    destino.mkdir(parents=True, exist_ok=True)
    dim.to_parquet(destino / "dim_classificacao.parquet", index=False)
    fato.to_parquet(destino / f"fato_{indice.codigo}.parquet", index=False)
    referencia.to_parquet(destino / f"ref_{indice.codigo}_geral.parquet", index=False)
    print(f"fato: {len(fato)} linhas; referência: {len(referencia)} meses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
