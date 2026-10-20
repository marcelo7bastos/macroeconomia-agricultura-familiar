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
from macroaf.indicators.difusao import montar_difusao
from macroaf.indicators.indice import (
    acumulado,
    acumulado_no_ano,
    marcar_cesta_variavel,
    montar_indice,
)
from macroaf.indicators.sazonalidade import ANOS, montar_sazonalidade
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


def _calcular_indicadores(indice: Indice, longa: pd.DataFrame, referencia: pd.DataFrame) -> dict:
    """Os indicadores do staging, calculados uma vez para a página."""
    excecoes = carregar_excecoes(indice)
    encadeado = montar_indice(longa, marcar_cesta_variavel(longa, excecoes))
    tabela_referencia = next(t.tabela for t in indice.tabelas if t.papel == "referencia")
    return {
        "indice": encadeado,
        "acumulados": montar_acumulados(encadeado, longa, referencia, excecoes, tabela_referencia),
        "contribuicoes": montar_contribuicoes(encadeado, longa),
        "difusao": montar_difusao(longa),
        "sazonalidade": montar_sazonalidade(encadeado),
    }


def _desvio_1117(encadeado: pd.DataFrame, referencia: pd.DataFrame) -> float:
    geral = encadeado[encadeado.codigo_ibge == "0"].set_index("mes").indice
    oficial = referencia.set_index("mes").numero_indice
    return float((geral / geral.iloc[0] * oficial.iloc[0] / oficial - 1).abs().max() * 100)


def _coletar_indice(ind: dict, referencia: pd.DataFrame) -> dict:
    encadeado = ind["indice"]
    return {
        "series": int(encadeado.serie_id.nunique()),
        "linhas": len(encadeado),
        "cesta_variavel": int(encadeado.cesta_variavel.sum()),
        "desvio_max_1117": _desvio_1117(encadeado, referencia),
    }


def _coletar_acumulados(ind: dict) -> dict:
    acumulados = ind["acumulados"]
    contagem = acumulados.groupby(["janela", "origem"]).size().unstack(fill_value=0)
    contagem = contagem.reindex(index=list(JANELAS), columns=["oficial", "calculado"], fill_value=0)
    return {
        "linhas": len(acumulados),
        "janelas": [[j, int(r.oficial), int(r.calculado)] for j, r in contagem.iterrows()],
    }


def _diferenca_grupos_geral(contribuicoes: pd.DataFrame) -> pd.Series:
    """Maior |soma dos grupos - geral| por janela, em p.p."""
    grupos = (
        contribuicoes[contribuicoes.nivel_hierarquico == "grupo"]
        .groupby(["janela", "mes"])
        .contribuicao.sum()
    )
    geral = contribuicoes[contribuicoes.codigo_ibge == "0"].set_index(["janela", "mes"])
    return (grupos - geral.contribuicao.reindex(grupos.index)).abs().groupby("janela").max()


def _coletar_contribuicoes(ind: dict) -> dict:
    return {
        "linhas": len(ind["contribuicoes"]),
        "diferenca_max_mes": float(_diferenca_grupos_geral(ind["contribuicoes"])["mes"]),
    }


def _coletar_difusao(ind: dict) -> dict:
    geral = ind["difusao"][ind["difusao"].codigo_ibge == "0"].sort_values("mes")
    return {
        "anos": ANOS,
        "meses": int(geral.mes.nunique()),
        "ultimo_mes": geral.mes.iloc[-1],
        "ultima_simples": float(geral.difusao_simples.iloc[-1]),
        "linhas_sazonalidade": len(ind["sazonalidade"]),
    }


def _r(valor, casas: int = 2):
    return None if pd.isna(valor) else round(float(valor), casas)


def _exemplo_ancora(longa: pd.DataFrame, acumulados: pd.DataFrame) -> dict | None:
    """Série emendada que muda de código no ano da troca: 356 publicada x acumulado (A-023)."""
    ano = acumulados[acumulados.janela == "ano"]
    chave = [longa.serie_id, longa.mes.str[:4]]
    codigo_janeiro = longa.groupby(chave).codigo_ibge.transform("first")
    mudou = longa[(codigo_janeiro != longa.codigo_ibge) & longa.variacao_acum_ano.notna()]
    if mudou.empty:
        return None
    junto = mudou.merge(ano[["serie_id", "mes", "acumulado"]], on=["serie_id", "mes"])
    junto["diferenca"] = (junto.acumulado - junto.variacao_acum_ano).abs()
    fim_do_ano = junto[junto.mes.str[5:] == "12"]
    if fim_do_ano.empty:  # troca de POF no ano corrente, ainda sem dezembro
        return None
    maior = fim_do_ano.loc[fim_do_ano.diferenca.idxmax()]
    serie_id, ano_da_troca = maior.serie_id, maior.mes[:4]
    escolhida = junto[
        (junto.serie_id == serie_id) & (junto.mes.str[:4] == ano_da_troca)
    ].sort_values("mes")
    janeiro = longa[(longa.serie_id == serie_id) & (longa.mes == ano_da_troca + "-01")]
    return {
        "serie_id": serie_id,
        "nome_antes": janeiro.nome.iloc[0] if len(janeiro) else None,
        "nome_depois": escolhida.nome.iloc[0],
        "linhas": [
            [m, _r(v), _r(p), _r(a)]
            for m, v, p, a in zip(
                escolhida.mes,
                escolhida.variacao_mensal,
                escolhida.variacao_acum_ano,
                escolhida.acumulado,
                strict=True,
            )
        ],
    }


def _coletar_resultados(
    ind: dict, longa: pd.DataFrame, referencia: pd.DataFrame, excecoes: pd.DataFrame
) -> dict:
    """Números para os gráficos e as conferências da seção Resultados."""
    acumulados, contribuicoes = ind["acumulados"], ind["contribuicoes"]
    geral = acumulados[acumulados.codigo_ibge == "0"]
    doze = geral[geral.janela == "12m"].sort_values("mes")
    ultimo = longa.mes.max()
    grupos = longa[(longa.nivel_hierarquico == "grupo") & (longa.mes == ultimo)].sort_values(
        "codigo_ibge"
    )
    contrib = contribuicoes[
        (contribuicoes.nivel_hierarquico == "grupo") & (contribuicoes.mes == ultimo)
    ].pivot(index="codigo_ibge", columns="janela", values="contribuicao")
    difusao = ind["difusao"][ind["difusao"].codigo_ibge == "0"].sort_values("mes")
    saz = ind["sazonalidade"]
    saz_geral = saz[saz.codigo_ibge == "0"]
    completos = saz_geral.groupby("ano_final").mes_do_ano.nunique()
    ano_final = int(completos[completos == 12].index.max())  # último ano com os 12 meses
    saz_geral = saz_geral[saz_geral.ano_final == ano_final].sort_values("mes_do_ano")

    # Conferências: o calculado pelo índice contra o oficial, onde os dois existem.
    oficiais = acumulados[(acumulados.origem == "oficial") & ~acumulados.cesta_variavel]
    partes = []
    for janela, meses in JANELAS.items():
        dados = ind["indice"]
        calc = acumulado_no_ano(dados) if meses is None else acumulado(dados, meses)
        calculado = dados[["serie_id", "mes"]].assign(janela=janela, calculado=calc)
        partes.append(oficiais.merge(calculado, on=["serie_id", "mes", "janela"]))
    comparados = pd.concat(partes).dropna(subset=["calculado"])
    comparados["diferenca"] = (comparados.acumulado - comparados.calculado).abs()
    do_geral = comparados[comparados.codigo_ibge == "0"]
    doze_categorias = comparados[(comparados.codigo_ibge != "0") & (comparados.janela == "12m")]
    diferencas = _diferenca_grupos_geral(contribuicoes)
    conferencias = {
        "desvio_1117": _desvio_1117(ind["indice"], referencia),
        "geral_valores": len(do_geral),
        "erros_3065": int(
            sum(
                len(e.meses_com_erro_publicado)
                for e in excecoes.itertuples()
                if e.validacao.startswith("costura_acum")
            )
        ),
        "geral_diferenca": float(do_geral.diferenca.max()),
        "doze_valores": len(doze_categorias),
        "doze_diferenca": float(doze_categorias.diferenca.max()),
        "grupos_meses": int(contribuicoes[contribuicoes.janela == "mes"].mes.nunique()),
        "grupos_mes": float(diferencas["mes"]),
        "grupos_acumulados": float(diferencas.drop("mes").max()),
    }
    return {
        "ultimo_mes": ultimo,
        "doze_meses": [[m, _r(v)] for m, v in zip(doze.mes, doze.acumulado, strict=True)],
        "grupos": [
            {
                "codigo": g.codigo_ibge,
                "nome": g.nome,
                "peso": _r(g.peso),
                "variacao": _r(g.variacao_mensal),
                "contribuicao_mes": _r(contrib.loc[g.codigo_ibge, "mes"], 3),
                "contribuicao_12m": _r(contrib.loc[g.codigo_ibge, "12m"], 3),
            }
            for g in grupos.itertuples()
        ],
        "geral_mes": _r(
            longa[(longa.codigo_ibge == "0") & (longa.mes == ultimo)].variacao_mensal.iloc[0]
        ),
        "geral_12m": _r(doze.acumulado.iloc[-1]),
        "difusao": [
            [m, _r(s, 1), _r(p, 1)]
            for m, s, p in zip(
                difusao.mes, difusao.difusao_simples, difusao.difusao_ponderada, strict=True
            )
        ],
        "trocas": sorted(difusao[difusao.cesta_nova].mes),
        "sazonalidade": {
            "ano_final": ano_final,
            "anos": ANOS,
            "meses": [
                [m, _r(a), _r(b)]
                for m, a, b in zip(
                    saz_geral.mes_do_ano, saz_geral.media, saz_geral.mediana, strict=True
                )
            ],
        },
        "conferencias": conferencias,
        "ancora": _exemplo_ancora(longa, acumulados),
    }


def _completar_rastreios(rastreios: list[dict], ind: dict) -> None:
    """Leva o rastreio do leite do fato até o índice, o acumulado e a contribuição."""
    encadeado, acumulados, contrib = ind["indice"], ind["acumulados"], ind["contribuicoes"]
    for r in rastreios:
        chave = (
            (encadeado.tabela_sidra == r["tabela"])
            & (encadeado.codigo_sidra == r["dim"]["codigo_sidra"])
            & (encadeado.mes == r["mes"])
        )
        linha = encadeado[chave].iloc[0]
        serie = encadeado[encadeado.serie_id == linha.serie_id]

        def valor(tabela, janela, coluna, linha=linha):
            achado = tabela[
                (tabela.serie_id == linha.serie_id)
                & (tabela.mes == linha.mes)
                & (tabela.janela == janela)
            ]
            return None if achado.empty else achado.iloc[0][coluna]

        r["indicadores"] = {
            "serie_id": linha.serie_id,
            "serie_inicio": serie.mes.min(),
            "serie_fim": serie.mes.max(),
            "indice_base_100": _r(linha.indice, 4),
            "acumulado_12m": _r(valor(acumulados, "12m", "acumulado")),
            "origem_12m": valor(acumulados, "12m", "origem"),
            "contribuicao_mes_pp": _r(valor(contrib, "mes", "contribuicao"), 4),
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
    # Transição da linha "novo" (sem origem): a tabela anterior à de destino; da linha
    # "descontinuado" (sem destino): a tabela seguinte à de origem.
    tabelas = [t.tabela for t in indice.tabelas_dados]
    anterior = {d: o for o, d in pairwise(tabelas)}
    seguinte = dict(pairwise(tabelas))
    mapa.loc[mapa.tabela_destino.isna(), "transicao"] = [
        f"{pofs[int(o)]} → {pofs[seguinte[int(o)]]}"
        for o in mapa.loc[mapa.tabela_destino.isna(), "tabela_origem"]
    ]
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

    harmonizacao = encadeado = acumulados = contribuicoes = difusao = numeros = None
    if caminho_mapa(indice).exists():
        longa = montar_serie_longa(fato, dim, ler_mapa(indice))
        harmonizacao = _coletar_harmonizacao(indice, fato, longa)
        ind = _calcular_indicadores(indice, longa, referencia)
        encadeado = _coletar_indice(ind, referencia)
        acumulados = _coletar_acumulados(ind)
        contribuicoes = _coletar_contribuicoes(ind)
        difusao = _coletar_difusao(ind)
        numeros = _coletar_resultados(ind, longa, referencia, carregar_excecoes(indice))
        _completar_rastreios(rastreios, ind)
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
        "difusao": difusao,
        "resultados": numeros,
        "marts": sorted(p.name for p in (RAIZ / "data" / "marts").glob(f"{indice.codigo}*")),
    }
