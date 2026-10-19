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

import pandas as pd

from macroaf.catalogo import RAIZ, Indice, carregar_catalogo
from macroaf.extract.raw import METADADOS, ArmazemRaw
from macroaf.transform.classificacao import NIVEIS, montar_dim_classificacao
from macroaf.transform.ipca15 import montar_fato, montar_referencia
from macroaf.validate.ipca15 import carregar_configuracao, validar

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
        "marts": sorted(p.name for p in (RAIZ / "data" / "marts").glob(f"{indice.codigo}*")),
    }
