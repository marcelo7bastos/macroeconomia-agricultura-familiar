"""Coleta os fatos que a página de transformações mostra, direto do repositório.

Nada aqui é escrito à mão: números, períodos, exceções, decisões e lições vêm do catálogo, do raw,
do staging, das validações e dos documentos do projeto. Se a fonte muda, a página muda; se a
página não for regerada, o teste `tests/test_relatorio_transformacoes.py` falha.
"""

from __future__ import annotations

import gzip
import json
import re
from dataclasses import asdict
from itertools import pairwise

import pandas as pd

from macroaf.catalogo import RAIZ, Indice, carregar_catalogo
from macroaf.extract.raw import METADADOS, ArmazemRaw
from macroaf.indicators.acumulados import JANELAS, montar_acumulados
from macroaf.indicators.contribuicoes import montar_contribuicoes
from macroaf.indicators.indice import marcar_cesta_variavel, montar_indice
from macroaf.transform.classificacao import NIVEIS, montar_dim_classificacao
from macroaf.transform.harmonizacao import caminho_mapa, id_ligacao, ler_mapa, montar_serie_longa
from macroaf.transform.ipca15 import montar_fato, montar_referencia
from macroaf.validate.ipca15 import carregar_configuracao, carregar_excecoes, validar

COLUNAS_MEDIDA = ["variacao_mensal", "variacao_acum_ano", "variacao_acum_12m", "peso"]


def _ler(caminho) -> str:
    return (RAIZ / caminho).read_text(encoding="utf-8")


def _tabela_markdown(texto: str, titulo_secao: str) -> list[list[str]]:
    """Linhas de dados da primeira tabela Markdown depois do título indicado."""
    inicio = texto.index(titulo_secao)
    linhas = []
    for linha in texto[inicio:].splitlines()[1:]:
        if linha.startswith("|"):
            celulas = [c.strip() for c in linha.strip("|").split("|")]
            if not set("".join(celulas)) <= set("-: "):
                linhas.append(celulas)
        elif linhas:
            break
    return linhas[1:]  # sem o cabeçalho


def _sem_markdown(texto: str) -> str:
    texto = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", texto)
    return texto.replace("**", "").replace("`", "")


def coletar_aprendizados() -> list[dict]:
    padrao = re.compile(r"^### (A-\d{3}) · (\d{4}-\d{2}-\d{2}) · (.+)$", re.MULTILINE)
    return [
        {"codigo": c, "data": d, "titulo": _sem_markdown(t)}
        for c, d, t in padrao.findall(_ler("docs/aprendizados.md"))
    ]


def coletar_decisoes() -> list[dict]:
    linhas = _tabela_markdown(_ler("docs/PLANEJAMENTO.md"), "## 9. Decisões")
    return [
        {"numero": n, "tema": _sem_markdown(t), "decisao": _sem_markdown(d)} for n, t, d in linhas
    ]


def coletar_indicadores_planejados() -> list[dict]:
    linhas = _tabela_markdown(_ler("docs/PLANEJAMENTO.md"), "### 5.2 Calculados")
    return [
        {"indicador": _sem_markdown(i), "definicao": _sem_markdown(d), "teste": _sem_markdown(t)}
        for i, d, t in linhas
    ]


def coletar_agentes() -> list[dict]:
    agentes = []
    for arquivo in sorted((RAIZ / ".claude" / "agents").glob("*.md")):
        cabecalho = arquivo.read_text(encoding="utf-8").split("---")[1]
        campos = dict(re.findall(r"^(\w+): (.+)$", cabecalho, re.MULTILINE))
        agentes.append({"nome": campos["name"], "descricao": campos["description"]})
    return agentes


def _amostra_raw(armazem: ArmazemRaw, tabela: int, periodo: str, codigo_sidra: int) -> list[dict]:
    dados = json.loads(armazem.ler(armazem.vigente(tabela, periodo)))
    return [r for r in dados[1:] if r.get("D4C") == str(codigo_sidra)]


def _texto(valor) -> str | None:
    return None if valor is None or (isinstance(valor, float) and pd.isna(valor)) else str(valor)


def _coletar_indice(indice: Indice, longa: pd.DataFrame, referencia: pd.DataFrame) -> dict:
    marcas = marcar_cesta_variavel(longa, carregar_excecoes(indice))
    encadeado = montar_indice(longa, marcas)
    geral = encadeado[encadeado.codigo_ibge == "0"].set_index("mes").indice
    oficial = referencia.set_index("mes").numero_indice
    desvio = (geral / geral.iloc[0] * oficial.iloc[0] / oficial - 1).abs()
    return {
        "series": int(encadeado.serie_id.nunique()),
        "linhas": len(encadeado),
        "cesta_variavel": int(encadeado.cesta_variavel.sum()),
        "desvio_max_1117": float(desvio.max() * 100),
    }


def _coletar_acumulados(indice: Indice, longa: pd.DataFrame, referencia: pd.DataFrame) -> dict:
    excecoes = carregar_excecoes(indice)
    encadeado = montar_indice(longa, marcar_cesta_variavel(longa, excecoes))
    tabela_referencia = next(t.tabela for t in indice.tabelas if t.papel == "referencia")
    acumulados = montar_acumulados(encadeado, longa, referencia, excecoes, tabela_referencia)
    contagem = acumulados.groupby(["janela", "origem"]).size().unstack(fill_value=0)
    contagem = contagem.reindex(index=list(JANELAS), columns=["oficial", "calculado"], fill_value=0)
    return {
        "linhas": len(acumulados),
        "janelas": [[j, int(r.oficial), int(r.calculado)] for j, r in contagem.iterrows()],
    }


def _coletar_contribuicoes(indice: Indice, longa: pd.DataFrame) -> dict:
    encadeado = montar_indice(longa, marcar_cesta_variavel(longa, carregar_excecoes(indice)))
    contribuicoes = montar_contribuicoes(encadeado, longa)
    mensais = contribuicoes[contribuicoes.janela == "mes"]
    grupos = mensais[mensais.nivel_hierarquico == "grupo"].groupby("mes").contribuicao.sum()
    geral = mensais[mensais.codigo_ibge == "0"].set_index("mes").contribuicao
    return {
        "linhas": len(contribuicoes),
        "diferenca_max_mes": float((grupos - geral).abs().max()),
    }


def _coletar_harmonizacao(indice: Indice, fato: pd.DataFrame, longa: pd.DataFrame) -> dict:
    mapa = ler_mapa(indice)
    pofs = {t.tabela: t.versao_pof for t in indice.tabelas_dados}
    mapa = mapa.assign(
        transicao=[
            f"{pofs.get(o, '?')} → {pofs.get(d, '?')}"
            for o, d in zip(
                mapa.tabela_origem.fillna(-1).astype(int),
                mapa.tabela_destino.fillna(-1).astype(int),
                strict=True,
            )
        ]
    )
    # Transição da linha "novo" (sem origem): a tabela anterior à de destino.
    tabelas = [t.tabela for t in indice.tabelas_dados]
    anterior = {d: o for o, d in pairwise(tabelas)}
    mapa.loc[mapa.tabela_origem.isna(), "transicao"] = [
        f"{pofs[anterior[int(d)]]} → {pofs[int(d)]}"
        for d in mapa.loc[mapa.tabela_origem.isna(), "tabela_destino"]
    ]
    contagem = (
        mapa.groupby(["transicao", "situacao", "tipo_correspondencia"])
        .size()
        .reset_index(name="n")
        .to_dict("records")
    )

    def registro(r) -> dict:
        return {
            "id": id_ligacao(r),
            "transicao": r.transicao,
            "nivel": r.nivel_hierarquico,
            "tipo": r.tipo_correspondencia,
            "situacao": r.situacao,
            "origem": None
            if pd.isna(r.codigo_sidra_origem)
            else f"{r.codigo_ibge_origem} {r.nome_origem} (id {int(r.codigo_sidra_origem)})",
            "destino": None
            if pd.isna(r.codigo_sidra_destino)
            else f"{r.codigo_ibge_destino} {r.nome_destino} (id {int(r.codigo_sidra_destino)})",
            "criterio": r.criterio,
            "peso_origem_fim": None
            if pd.isna(r.peso_origem_fim)
            else round(float(r.peso_origem_fim), 4),
            "peso_destino_inicio": None
            if pd.isna(r.peso_destino_inicio)
            else round(float(r.peso_destino_inicio), 4),
            "revisor": _texto(r.revisor),
            "observacao": _texto(r.observacao),
        }

    revisar = mapa[mapa.situacao.isin(["proposto", "revisado", "rejeitado"])].sort_values(
        ["transicao", "codigo_ibge_origem"]
    )
    entram_saem = mapa[mapa.tipo_correspondencia.isin(["descontinuado", "novo"])].sort_values(
        ["transicao", "codigo_ibge_origem", "codigo_ibge_destino"]
    )
    series = longa.drop_duplicates("serie_id")
    completas = series[
        (series.inicio_serie == fato.mes.min()) & (series.fim_serie == fato.mes.max())
    ]
    return {
        "linhas": len(mapa),
        "contagem": contagem,
        "propostas": [registro(r) for r in revisar.itertuples()],
        "entram_saem": [registro(r) for r in entram_saem.itertuples()],
        "series": {
            "total": int(series.serie_id.nunique()),
            "por_nivel": series.nivel_hierarquico.value_counts()
            .reindex(NIVEIS)
            .fillna(0)
            .astype(int)
            .to_dict(),
            "completas_por_nivel": completas.nivel_hierarquico.value_counts()
            .reindex(NIVEIS)
            .fillna(0)
            .astype(int)
            .to_dict(),
            "linhas": len(longa),
        },
    }


def coletar(indice: Indice) -> dict:
    catalogo = carregar_catalogo()
    armazem = ArmazemRaw(indice.fonte)
    dim = montar_dim_classificacao(indice, armazem)
    fato = montar_fato(indice, armazem, dim)
    referencia = montar_referencia(indice, armazem)
    configuracao = carregar_configuracao(indice, armazem, dim)
    resultados, sentinelas = validar(fato, referencia, configuracao)
    manifesto = pd.DataFrame(armazem.ler_manifesto())
    manifesto["n_registros"] = manifesto.n_registros.astype(int)
    manifesto["bytes"] = manifesto.bytes.astype(int)
    tamanho_raw = sum(p.stat().st_size for p in armazem.diretorio.glob("*/*.json.gz"))

    tabelas = []
    for tabela in indice.tabelas:
        meses = armazem.periodos(tabela.tabela)
        do_manifesto = manifesto[
            (manifesto.tabela == str(tabela.tabela)) & (manifesto.periodo != METADADOS)
        ]
        da_dim = dim[dim.tabela_sidra == tabela.tabela]
        do_fato = fato[fato.tabela_sidra == tabela.tabela]
        tabelas.append(
            {
                "tabela": tabela.tabela,
                "papel": tabela.papel,
                "versao_pof": tabela.versao_pof,
                "inicio": tabela.inicio,
                "fim": tabela.fim or (meses[-1] if meses else None),
                "aberta": tabela.fim is None,
                "variaveis": [
                    {"codigo": v, "nome": indice.variaveis[v].nome} for v in tabela.variaveis
                ],
                "meses_raw": len(meses),
                "registros_raw": int(do_manifesto.n_registros.sum()),
                "bytes_json": int(do_manifesto.bytes.sum()),
                "categorias": {n: int((da_dim.nivel_hierarquico == n).sum()) for n in NIVEIS},
                "linhas_fato": len(do_fato),
                "cobertura": {
                    c: round(float(do_fato[c].notna().mean()) * 100, 1) if len(do_fato) else None
                    for c in COLUNAS_MEDIDA
                },
            }
        )

    # Mesmo código IBGE com id SIDRA diferente entre tabelas (A-012).
    ids = dim.groupby("codigo_ibge").codigo_sidra.nunique()
    trocas = dim[dim.codigo_ibge.isin(ids[ids > 1].index)]
    exemplos_id = []
    for codigo in ["1111004", "1114083", "1101073", "3202028"]:
        linhas = trocas[trocas.codigo_ibge == codigo].sort_values(
            "tabela_sidra", key=lambda s: s.map({t.tabela: i for i, t in enumerate(indice.tabelas)})
        )
        if not linhas.empty:
            exemplos_id.append(
                {
                    "codigo_ibge": codigo,
                    "versoes": linhas[["tabela_sidra", "codigo_sidra", "nome"]].to_dict("records"),
                }
            )

    # Rastreio de um valor: do raw ao fato, para o leite (1111004) no último mês de cada tabela.
    rastreios = []
    for tabela in indice.tabelas_dados:
        meses = armazem.periodos(tabela.tabela)
        linha_dim = dim[(dim.tabela_sidra == tabela.tabela) & (dim.codigo_ibge == "1111004")]
        if not meses or linha_dim.empty:
            continue
        mes = meses[-1]
        codigo_sidra = int(linha_dim.codigo_sidra.iloc[0])
        linha_fato = fato[
            (fato.tabela_sidra == tabela.tabela)
            & (fato.mes == mes)
            & (fato.codigo_sidra == codigo_sidra)
        ]
        rastreios.append(
            {
                "tabela": tabela.tabela,
                "mes": mes,
                "arquivo": f"data/raw/{indice.fonte}/{tabela.tabela}/{mes.replace('-', '')}"
                ".json.gz",
                "raw": _amostra_raw(armazem, tabela.tabela, mes, codigo_sidra),
                "dim": linha_dim.iloc[0].to_dict(),
                "fato": linha_fato.iloc[0].replace({float("nan"): None}).to_dict(),
            }
        )

    harmonizacao = encadeado = acumulados = contribuicoes = None
    if caminho_mapa(indice).exists():
        longa = montar_serie_longa(fato, dim, ler_mapa(indice))
        harmonizacao = _coletar_harmonizacao(indice, fato, longa)
        encadeado = _coletar_indice(indice, longa, referencia)
        acumulados = _coletar_acumulados(indice, longa, referencia)
        contribuicoes = _coletar_contribuicoes(indice, longa)
    geral = referencia.iloc[-1].to_dict()
    excecoes = configuracao.excecoes.drop(columns=[]).to_dict("records")
    limites = configuracao.limites.to_dict("records")
    meta_7062 = next(t for t in indice.tabelas_dados if t.fim is None)
    metadados = json.loads(
        gzip.decompress(
            (armazem.diretorio / str(meta_7062.tabela) / "metadados.json.gz").read_bytes()
        )
    )

    return {
        "indice": {
            "codigo": indice.codigo,
            "nome": indice.nome,
            "descricao": indice.descricao,
            "fonte": catalogo.fontes[indice.fonte].nome,
            "classificacao": indice.classificacao,
            "nome_classificacao": metadados["classificacoes"][0]["nome"],
        },
        "periodo": {"inicio": referencia.mes.iloc[0], "fim": referencia.mes.iloc[-1]},
        "raw": {
            "arquivos": len(manifesto),
            "registros": int(manifesto.n_registros.sum()),
            "megabytes_json": round(manifesto.bytes.sum() / 1e6, 1),
            "megabytes_gzip": round(tamanho_raw / 1e6, 1),
            "revisoes": int((manifesto.revisao.astype(int) > 1).sum()),
        },
        "tabelas": tabelas,
        "dim": {
            "linhas": len(dim),
            "trocas_de_id": int((ids > 1).sum()),
            "trocas_por_nivel": trocas.drop_duplicates("codigo_ibge")
            .nivel_hierarquico.value_counts()
            .to_dict(),
            "exemplos_id": exemplos_id,
        },
        "fato": {"linhas": len(fato), "colunas": list(fato.columns)},
        "referencia": {
            "meses": len(referencia),
            "colunas": list(referencia.columns),
            "ultimo": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in geral.items()},
        },
        "rastreios": rastreios,
        "validacoes": [asdict(r) | {"ok": r.ok} for r in resultados],
        "sentinelas": len(sentinelas),
        "excecoes": excecoes,
        "limites": limites,
        "aprendizados": coletar_aprendizados(),
        "decisoes": coletar_decisoes(),
        "indicadores_planejados": coletar_indicadores_planejados(),
        "agentes": coletar_agentes(),
        "harmonizacao": harmonizacao,
        "indice_encadeado": encadeado,
        "acumulados": acumulados,
        "contribuicoes": contribuicoes,
        "marts": sorted(p.name for p in (RAIZ / "data" / "marts").glob(f"{indice.codigo}*")),
    }
