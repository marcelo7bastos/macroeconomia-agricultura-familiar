"""`map_harmonizacao` entre POFs consecutivas e a série longa que dele resulta.

Princípio: **na dúvida, quebra** (METODOLOGIA.md, seção 7). Emendar duas categorias numa série
contínua exige prova: o mesmo id SIDRA (`identico`) ou uma revisão humana registrada. Encerrar
uma série nunca esconde nada; emendar errado esconde. Por isso:

- mesmo código IBGE e mesmo id SIDRA → `identico`, automático (o id identifica a definição, A-012);
- mesmo código e id novo com nome igual depois de normalizar acentos e pontuação → `renomeado`,
  automático (só grafia);
- mesmo código e id novo com nome diferente → **proposta** para revisão (renomeado, fundido...);
- código que some ou aparece com candidato de nome parecido no mesmo item → **proposta** de
  `fundido` ou `dividido`; sem candidato → `descontinuado` ou `novo`, automático.

Proposta não revisada é tratada como quebra. A revisão fica em
`reference/map_harmonizacao_<indice>.csv` (coluna `situacao = revisado`) e é preservada quando o
mapa é regerado.

Uso:

    uv run python -m macroaf.transform.harmonizacao     # atualiza o mapa e grava a série longa
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import unicodedata
from itertools import pairwise
from pathlib import Path

import pandas as pd

from macroaf.catalogo import RAIZ, Indice, carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.transform.classificacao import montar_dim_classificacao
from macroaf.transform.ipca15 import montar_fato

TIPOS = ["identico", "renomeado", "dividido", "fundido", "descontinuado", "novo"]
CONTINUOS = {"identico", "renomeado"}
SITUACOES = ["automatico", "proposto", "revisado"]
PARENTESCO_CANDIDATO = 0.5
PALAVRAS_VAZIAS = {"de", "da", "do", "das", "dos", "e", "em", "para", "com", "sem", "a", "o"}
COLUNAS_MAPA = [
    "versao_pof_origem",
    "tabela_origem",
    "codigo_ibge_origem",
    "codigo_sidra_origem",
    "nome_origem",
    "versao_pof_destino",
    "tabela_destino",
    "codigo_ibge_destino",
    "codigo_sidra_destino",
    "nome_destino",
    "nivel_hierarquico",
    "tipo_correspondencia",
    "situacao",
    "criterio",
    "peso_origem_fim",
    "peso_destino_inicio",
    "revisor",
    "observacao",
]
CHAVE = ["tabela_origem", "codigo_sidra_origem", "tabela_destino", "codigo_sidra_destino"]


class ErroHarmonizacao(ValueError):
    """O mapa de harmonização está incompleto ou incoerente."""


def normalizar_nome(nome: str) -> str:
    """Minúsculas, sem acento e sem pontuação: só para comparar grafias."""
    sem_acento = unicodedata.normalize("NFKD", nome.lower())
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", sem_acento).strip()


def similaridade(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalizar_nome(a), normalizar_nome(b)).ratio()


def _palavras(nome: str) -> set[str]:
    return {p for p in normalizar_nome(nome).split() if p not in PALAVRAS_VAZIAS}


def parentesco(a: str, b: str) -> float:
    """Proximidade de dois nomes: 1 se iguais depois de normalizar; senão, a fração das palavras do
    nome menor que aparece no maior (pega "Livro" → "Livro didático" e evita "Melão" → "Telha")."""
    if normalizar_nome(a) == normalizar_nome(b):
        return 1.0
    pa, pb = _palavras(a), _palavras(b)
    if not pa or not pb:
        return 0.0
    menor, maior = sorted([pa, pb], key=len)
    comum = len(menor & maior) / len(menor)
    # Uma palavra genérica em comum ("Peixe - x" e "Peixe - y") não basta: exige mais da metade
    # das palavras do nome maior ou todas as do menor.
    return comum if comum == 1.0 or len(menor & maior) / len(maior) > 0.5 else 0.0


def caminho_mapa(indice: Indice) -> Path:
    return RAIZ / "reference" / f"map_harmonizacao_{indice.codigo}.csv"


def _pesos_nas_pontas(fato: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Peso de cada categoria no último e no primeiro mês da sua tabela."""
    ultimo = fato.groupby("tabela_sidra").mes.transform("max")
    primeiro = fato.groupby("tabela_sidra").mes.transform("min")
    chave = ["tabela_sidra", "codigo_sidra"]
    fim = fato[fato.mes == ultimo].set_index(chave).peso
    inicio = fato[fato.mes == primeiro].set_index(chave).peso
    return fim, inicio


def _linha(origem, destino, tipo, situacao, criterio, pesos) -> dict:
    fim, inicio = pesos
    return {
        "versao_pof_origem": None if origem is None else origem.versao_pof,
        "tabela_origem": None if origem is None else origem.tabela_sidra,
        "codigo_ibge_origem": None if origem is None else origem.codigo_ibge,
        "codigo_sidra_origem": None if origem is None else origem.codigo_sidra,
        "nome_origem": None if origem is None else origem.nome,
        "versao_pof_destino": None if destino is None else destino.versao_pof,
        "tabela_destino": None if destino is None else destino.tabela_sidra,
        "codigo_ibge_destino": None if destino is None else destino.codigo_ibge,
        "codigo_sidra_destino": None if destino is None else destino.codigo_sidra,
        "nome_destino": None if destino is None else destino.nome,
        "nivel_hierarquico": (origem if origem is not None else destino).nivel_hierarquico,
        "tipo_correspondencia": tipo,
        "situacao": situacao,
        "criterio": criterio,
        "peso_origem_fim": None
        if origem is None
        else fim.get((origem.tabela_sidra, origem.codigo_sidra)),
        "peso_destino_inicio": None
        if destino is None
        else inicio.get((destino.tabela_sidra, destino.codigo_sidra)),
        "revisor": None,
        "observacao": None,
    }


def _item_de(linha) -> str | None:
    return linha.item if linha.nivel_hierarquico == "subitem" else linha.subgrupo


def _classificar_mesmo_codigo(origem, destino) -> tuple[str, str, str]:
    """Tipo, situação e critério para um código presente nas duas tabelas."""
    if destino.codigo_sidra == origem.codigo_sidra:
        return "identico", "automatico", "mesmo código e mesmo id SIDRA"
    if normalizar_nome(origem.nome) == normalizar_nome(destino.nome):
        return "renomeado", "automatico", "mesmo código; id novo; só grafia mudou"
    nota = similaridade(origem.nome, destino.nome)
    return "renomeado", "proposto", f"mesmo código; id novo; nome mudou (similaridade {nota:.2f})"


def _candidatos(saem: list, entram: list) -> list[tuple]:
    """Pares (origem, destino, parentesco) com evidência forte: nome igual depois de normalizar,
    em qualquer lugar da árvore, ou palavras em comum dentro do mesmo item."""
    pares = []
    for origem in saem:
        for destino in entram:
            if origem.nivel_hierarquico != destino.nivel_hierarquico:
                continue
            nota = parentesco(origem.nome, destino.nome)
            mesmo_nome = normalizar_nome(origem.nome) == normalizar_nome(destino.nome)
            mesma_familia = _item_de(origem) == _item_de(destino)
            if mesmo_nome or (mesma_familia and nota >= PARENTESCO_CANDIDATO):
                pares.append((origem, destino, nota))
    return pares


def propor_transicao(antes: pd.DataFrame, depois: pd.DataFrame, pesos) -> list[dict]:
    """Proposta de correspondências entre duas tabelas consecutivas (dim de cada uma)."""
    por_codigo_depois = {r.codigo_ibge: r for r in depois.itertuples()}
    codigos_antes = set(antes.codigo_ibge)
    linhas = [
        _linha(origem, por_codigo_depois[origem.codigo_ibge], *classificacao, pesos)
        for origem in antes.itertuples()
        if origem.codigo_ibge in por_codigo_depois
        for classificacao in [
            _classificar_mesmo_codigo(origem, por_codigo_depois[origem.codigo_ibge])
        ]
    ]

    saem = [r for r in antes.itertuples() if r.codigo_ibge not in por_codigo_depois]
    entram = [r for r in depois.itertuples() if r.codigo_ibge not in codigos_antes]
    pares = _candidatos(saem, entram)
    destinos_de, origens_de = {}, {}
    for origem, destino, _ in pares:
        destinos_de.setdefault(origem.codigo_sidra, []).append(destino)
        origens_de.setdefault(destino.codigo_sidra, []).append(origem)
    for origem, destino, nota in pares:
        n_destinos, n_origens = (
            len(destinos_de[origem.codigo_sidra]),
            len(origens_de[destino.codigo_sidra]),
        )
        tipo = "fundido" if n_origens > 1 else "dividido" if n_destinos > 1 else "renomeado"
        criterio = (
            f"código mudou; nome parecido (parentesco {nota:.2f}); "
            f"{n_origens} origem(ns) para {n_destinos} destino(s)"
        )
        linhas.append(_linha(origem, destino, tipo, "proposto", criterio, pesos))
    linhas += [
        _linha(o, None, "descontinuado", "automatico", "código some e não há candidato", pesos)
        for o in saem
        if o.codigo_sidra not in destinos_de
    ]
    linhas += [
        _linha(None, d, "novo", "automatico", "código aparece e não há candidato", pesos)
        for d in entram
        if d.codigo_sidra not in origens_de
    ]
    return linhas


def propor_mapa(indice: Indice, dim: pd.DataFrame, fato: pd.DataFrame) -> pd.DataFrame:
    pesos = _pesos_nas_pontas(fato)
    tabelas = [t.tabela for t in indice.tabelas_dados]
    linhas = []
    for antes, depois in pairwise(tabelas):
        linhas += propor_transicao(
            dim[dim.tabela_sidra == antes], dim[dim.tabela_sidra == depois], pesos
        )
    return _tipar(pd.DataFrame(linhas, columns=COLUNAS_MAPA))


def _tipar(mapa: pd.DataFrame) -> pd.DataFrame:
    for coluna in [
        "tabela_origem",
        "codigo_sidra_origem",
        "tabela_destino",
        "codigo_sidra_destino",
    ]:
        mapa[coluna] = mapa[coluna].astype("Int64")
    for coluna in ["peso_origem_fim", "peso_destino_inicio"]:
        mapa[coluna] = mapa[coluna].astype(float)
    numericas = {*CHAVE, "peso_origem_fim", "peso_destino_inicio"}
    textos = [c for c in COLUNAS_MAPA if c not in numericas]
    for coluna in textos:
        mapa[coluna] = mapa[coluna].astype(object).where(mapa[coluna].notna(), None)
    return mapa


def ler_mapa(indice: Indice) -> pd.DataFrame:
    caminho = caminho_mapa(indice)
    mapa = pd.read_csv(caminho, dtype={"codigo_ibge_origem": str, "codigo_ibge_destino": str})
    return _tipar(mapa[COLUNAS_MAPA])


def atualizar_mapa(proposta: pd.DataFrame, atual: pd.DataFrame | None) -> pd.DataFrame:
    """Mantém as linhas revisadas do mapa atual; o resto vem da proposta nova."""
    if atual is None or atual.empty:
        return proposta
    revisadas = atual[atual.situacao == "revisado"]
    # Uma revisão substitui toda proposta que envolva as mesmas categorias.
    tocadas = set()
    for r in revisadas.itertuples():
        if pd.notna(r.codigo_sidra_origem):
            tocadas.add(("origem", int(r.tabela_origem), int(r.codigo_sidra_origem)))
        if pd.notna(r.codigo_sidra_destino):
            tocadas.add(("destino", int(r.tabela_destino), int(r.codigo_sidra_destino)))

    def toca(r) -> bool:
        return (
            pd.notna(r.codigo_sidra_origem)
            and ("origem", int(r.tabela_origem), int(r.codigo_sidra_origem)) in tocadas
        ) or (
            pd.notna(r.codigo_sidra_destino)
            and ("destino", int(r.tabela_destino), int(r.codigo_sidra_destino)) in tocadas
        )

    restante = proposta[[not toca(r) for r in proposta.itertuples()]]
    return pd.concat([revisadas, restante], ignore_index=True)


def conferir_mapa(mapa: pd.DataFrame, dim: pd.DataFrame, indice: Indice) -> list[str]:
    """Problemas de completude e coerência do mapa (lista vazia = ok)."""
    problemas = []
    if not set(mapa.tipo_correspondencia) <= set(TIPOS):
        problemas.append(f"tipos inválidos: {set(mapa.tipo_correspondencia) - set(TIPOS)}")
    if not set(mapa.situacao) <= set(SITUACOES):
        problemas.append(f"situações inválidas: {set(mapa.situacao) - set(SITUACOES)}")
    revisadas_sem_revisor = mapa[(mapa.situacao == "revisado") & mapa.revisor.isna()]
    if not revisadas_sem_revisor.empty:
        problemas.append(f"{len(revisadas_sem_revisor)} linhas revisadas sem revisor")

    tabelas = [t.tabela for t in indice.tabelas_dados]
    for antes, depois in pairwise(tabelas):
        da_transicao = mapa[
            (mapa.tabela_origem == antes)
            | (mapa.tabela_origem.isna() & (mapa.tabela_destino == depois))
        ]
        for tabela, coluna in [(antes, "codigo_sidra_origem"), (depois, "codigo_sidra_destino")]:
            esperados = set(dim[dim.tabela_sidra == tabela].codigo_sidra)
            presentes = set(da_transicao[coluna].dropna().astype(int))
            if esperados - presentes:
                problemas.append(
                    f"{antes}->{depois}: {len(esperados - presentes)} categorias "
                    f"da {tabela} sem linha no mapa"
                )
        # Mesmo código com id diferente precisa estar no mapa com tipo explícito (A-012).
        continuos = da_transicao[da_transicao.tipo_correspondencia.isin(CONTINUOS)]
        for coluna in ["codigo_sidra_origem", "codigo_sidra_destino"]:
            confirmados = continuos[continuos.situacao != "proposto"]
            repetidos = confirmados[coluna].dropna().duplicated()
            if repetidos.any():
                problemas.append(
                    f"{antes}->{depois}: categoria com mais de uma continuação ({coluna})"
                )
    return problemas


def _continuidades(mapa: pd.DataFrame) -> pd.DataFrame:
    """Ligações que emendam a série: tipo contínuo e situação automática ou revisada."""
    return mapa[
        mapa.tipo_correspondencia.isin(CONTINUOS) & mapa.situacao.isin(["automatico", "revisado"])
    ]


def montar_serie_longa(fato: pd.DataFrame, dim: pd.DataFrame, mapa: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por mês e categoria, com o identificador da série longa a que pertence.

    `serie_id` = código IBGE e POF da primeira categoria da série (estável quando entra POF nova).
    `entrada` e `saida` dizem como a série começou e terminou: início ou fim dos dados, ou o tipo
    de correspondência que a interrompeu (quebra marcada, nunca emendada).
    """
    continuas = _continuidades(mapa)
    sucessor = {
        (int(r.tabela_origem), int(r.codigo_sidra_origem)): (
            int(r.tabela_destino),
            int(r.codigo_sidra_destino),
        )
        for r in continuas.itertuples()
    }
    tem_antecessor = set(sucessor.values())
    quebra_saida = {}
    quebra_entrada = {}
    for r in mapa.itertuples():
        nao_emenda = r.tipo_correspondencia not in CONTINUOS or r.situacao == "proposto"
        if not nao_emenda:
            continue
        rotulo = r.tipo_correspondencia + (
            " (proposta não revisada)" if r.situacao == "proposto" else ""
        )
        if pd.notna(r.codigo_sidra_origem):
            quebra_saida.setdefault((int(r.tabela_origem), int(r.codigo_sidra_origem)), rotulo)
        if pd.notna(r.codigo_sidra_destino):
            quebra_entrada.setdefault((int(r.tabela_destino), int(r.codigo_sidra_destino)), rotulo)

    categorias = dim.set_index(["tabela_sidra", "codigo_sidra"])
    serie_de = {}
    for chave in categorias.index:
        if chave in tem_antecessor:
            continue
        primeira = categorias.loc[chave]
        serie_id = f"{primeira.codigo_ibge}@{primeira.versao_pof}"
        atual = chave
        while atual is not None:
            serie_de[atual] = serie_id
            atual = sucessor.get(atual)

    longa = fato.copy()
    chaves = list(zip(longa.tabela_sidra, longa.codigo_sidra, strict=True))
    longa["serie_id"] = [serie_de[c] for c in chaves]
    longa = longa.merge(
        dim[["tabela_sidra", "codigo_sidra", "nome"]], on=["tabela_sidra", "codigo_sidra"]
    )
    primeiro_da_serie = longa.groupby("serie_id").mes.transform("min")
    ultimo_da_serie = longa.groupby("serie_id").mes.transform("max")
    inicio_dados, fim_dados = fato.mes.min(), fato.mes.max()

    primeira_chave = (
        longa.sort_values("mes").groupby("serie_id")[["tabela_sidra", "codigo_sidra"]].first()
    )
    ultima_chave = (
        longa.sort_values("mes").groupby("serie_id")[["tabela_sidra", "codigo_sidra"]].last()
    )
    entrada = {
        s: ("inicio dos dados" if longa_mes == inicio_dados else quebra_entrada.get((t, c), "novo"))
        for s, t, c, longa_mes in zip(
            primeira_chave.index,
            primeira_chave.tabela_sidra,
            primeira_chave.codigo_sidra,
            longa.groupby("serie_id").mes.min().reindex(primeira_chave.index),
            strict=True,
        )
    }
    saida = {
        s: ("em curso" if longa_mes == fim_dados else quebra_saida.get((t, c), "descontinuado"))
        for s, t, c, longa_mes in zip(
            ultima_chave.index,
            ultima_chave.tabela_sidra,
            ultima_chave.codigo_sidra,
            longa.groupby("serie_id").mes.max().reindex(ultima_chave.index),
            strict=True,
        )
    }
    longa["inicio_serie"] = primeiro_da_serie
    longa["fim_serie"] = ultimo_da_serie
    longa["entrada"] = longa.serie_id.map(entrada)
    longa["saida"] = longa.serie_id.map(saida)
    colunas = [
        "serie_id",
        "mes",
        "versao_pof",
        "tabela_sidra",
        "codigo_sidra",
        "codigo_ibge",
        "nome",
        "nivel_hierarquico",
        "variacao_mensal",
        "variacao_acum_ano",
        "variacao_acum_12m",
        "peso",
        "inicio_serie",
        "fim_serie",
        "entrada",
        "saida",
    ]
    return longa[colunas].sort_values(["serie_id", "mes"]).reset_index(drop=True)


def conferir_serie_longa(longa: pd.DataFrame, fato: pd.DataFrame) -> list[str]:
    """Invariantes da série longa (lista vazia = ok)."""
    problemas = []
    if len(longa) != len(fato) or longa.duplicated(["tabela_sidra", "codigo_sidra", "mes"]).any():
        problemas.append("cada linha do fato deve aparecer uma vez na série longa")
    if longa.duplicated(["serie_id", "mes"]).any():
        problemas.append("série com dois valores no mesmo mês")
    if (longa.groupby("serie_id").nivel_hierarquico.nunique() > 1).any():
        problemas.append("série que muda de nível hierárquico")
    meses = longa.groupby("serie_id").mes.agg(["min", "max", "nunique"])
    esperado = meses.apply(
        lambda r: (
            (int(r["max"][:4]) - int(r["min"][:4])) * 12 + int(r["max"][5:]) - int(r["min"][5:]) + 1
        ),
        axis=1,
    )
    lacunas = meses[meses["nunique"] != esperado]
    if not lacunas.empty:
        problemas.append(f"séries com mês faltando no meio: {list(lacunas.index[:5])}")
    return problemas


def caminho_serie_longa(indice: Indice) -> Path:
    return RAIZ / "data" / "staging" / indice.codigo / f"serie_longa_{indice.codigo}.parquet"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atualiza o map_harmonizacao (preserva revisões).")
    parser.add_argument("--indice", default="ipca15")
    args = parser.parse_args(argv)

    indice = carregar_catalogo().indices[args.indice]
    armazem = ArmazemRaw(indice.fonte)
    dim = montar_dim_classificacao(indice, armazem)
    fato = montar_fato(indice, armazem, dim)
    caminho = caminho_mapa(indice)
    atual = ler_mapa(indice) if caminho.exists() else None
    mapa = atualizar_mapa(propor_mapa(indice, dim, fato), atual)
    problemas = conferir_mapa(mapa, dim, indice)
    if problemas:
        print("\n".join(problemas), file=sys.stderr)
        return 1
    mapa = mapa.sort_values(
        ["tabela_origem", "nivel_hierarquico", "codigo_ibge_origem", "codigo_ibge_destino"],
        na_position="last",
    )
    caminho.write_text(mapa.to_csv(index=False, lineterminator="\n"), encoding="utf-8")
    longa = montar_serie_longa(fato, dim, ler_mapa(indice))
    problemas = conferir_serie_longa(longa, fato)
    if problemas:
        print("\n".join(problemas), file=sys.stderr)
        return 1
    caminho_serie_longa(indice).parent.mkdir(parents=True, exist_ok=True)
    longa.to_parquet(caminho_serie_longa(indice), index=False)
    contagem = mapa.groupby(["situacao", "tipo_correspondencia"]).size()
    print(contagem.to_string())
    print(f"{len(mapa)} linhas em {caminho.relative_to(RAIZ)}")
    print(f"série longa: {longa.serie_id.nunique()} séries, {len(longa)} linhas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
