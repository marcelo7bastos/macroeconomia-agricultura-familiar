"""Explicação para gestores, gerada dos CSVs publicados, sem consultar APIs.

Uso: uv run python -m macroaf.relatorios.gestao [--indice ipca|ipca15] [--verificar]
Sem --indice, gera as duas páginas e a entrada do portal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from html import escape
from pathlib import Path

import pandas as pd

from macroaf.catalogo import RAIZ, carregar_catalogo

REPOSITORIO = "https://github.com/marcelo7bastos/macroeconomia-agricultura-familiar"
ASSETS = Path(__file__).with_name("assets")
CODIGOS = ("0", "1", "11", "12")


def _ler_csv(caminho: Path) -> pd.DataFrame:
    return pd.read_csv(
        caminho, dtype={"chave_categoria": str, "codigo_ibge": str}, low_memory=False
    )


def coletar(codigo: str) -> dict:
    """Usa a publicação verificada; não converte ausências em zero nem recalcula oficiais."""
    indice = carregar_catalogo().indices[codigo]
    pasta = RAIZ / "data" / "marts"
    meta = json.loads((RAIZ / "data" / "metadata.json").read_text())[codigo]
    for nome, arquivo in meta["arquivos"].items():
        conteudo = (pasta / nome).read_bytes()
        if hashlib.sha256(conteudo).hexdigest() != arquivo["sha256"]:
            raise ValueError(
                f"{nome}: hash diferente da publicação; não gerar explicação inconsistente"
            )
    categorias = _ler_csv(pasta / f"{codigo}_categorias.csv")
    mensal = _ler_csv(pasta / f"{codigo}_mensal.csv").merge(
        categorias[["chave_categoria", "codigo_ibge", "nome", "nivel_hierarquico"]],
        on="chave_categoria",
        validate="many_to_one",
    )
    acumulados = _ler_csv(pasta / f"{codigo}_acumulados.csv")
    mensal = mensal.merge(
        acumulados, on=["mes", "chave_categoria"], how="left", validate="one_to_one"
    )
    colunas = ["mes", "codigo_ibge", "nome", "variacao_mensal", "peso", "contribuicao_pp"]
    colunas += ["acum_ano", "origem_ano", "acum_12m", "origem_12m"]
    recorte = mensal[mensal.codigo_ibge.isin(CODIGOS) | (mensal.nivel_hierarquico == "grupo")]
    linhas = json.loads(recorte[colunas].to_json(orient="records", force_ascii=False))
    mapa = pd.read_csv(RAIZ / "reference" / f"map_harmonizacao_{codigo}.csv")
    contagem = mapa.situacao.value_counts().to_dict()
    ultima = mensal[mensal.mes == meta["ultimo_mes"]]
    raw = pd.read_csv(RAIZ / "data" / "raw" / indice.fonte / "manifesto.csv")
    raw = raw[raw.tabela.isin([t.tabela for t in indice.tabelas])]
    dicionario = "README.md" if codigo == "ipca15" else f"{codigo}_README.md"
    return {
        "codigo": codigo,
        "nome": indice.nome,
        "inicio": min(t.inicio for t in indice.tabelas_dados),
        "fim": meta["ultimo_mes"],
        "coleta": meta["ultima_coleta"],
        "referencia": indice.tabelas_referencia[0].tabela,
        "linhas": meta["arquivos"][f"{codigo}_mensal.csv"]["linhas"],
        "meses": int(mensal.mes.nunique()),
        "subitens": int((ultima.nivel_hierarquico == "subitem").sum()),
        "raw": len(raw),
        "harmonizacao": {k: int(v) for k, v in contagem.items()},
        "validacoes": meta["validacoes"],
        "registros": linhas,
        "dicionario": dicionario,
        "repositorio": REPOSITORIO,
        "tabelas": [
            {"id": t.tabela, "inicio": t.inicio, "fim": t.fim, "papel": t.papel}
            for t in indice.tabelas
        ],
        "arquivos": meta["arquivos"],
    }


def gerar(codigo: str) -> str:
    dados = coletar(codigo)
    html = (ASSETS / "gestao.html").read_text()
    linhagem = ""
    if codigo == "ipca":
        linhagem = (
            '<a href="ipca-linhagem.html" class="acao" '
            'aria-label="Abrir dicionário e linhagem do IPCA Geral">'
            "07 · Dicionário e linhagem ↗</a>"
        )
    substituicoes = {
        "NOME": escape(dados["nome"]),
        "CODIGO": codigo,
        "LINHAGEM": linhagem,
        "DADOS": json.dumps(dados, ensure_ascii=False, allow_nan=False).replace("</", "<\\/"),
        "CSS": (ASSETS / "gestao.css").read_text(),
        "JS": (ASSETS / "gestao.js").read_text(),
    }
    for chave, valor in substituicoes.items():
        html = html.replace(f"@@{chave}@@", valor)
    return html


def gerar_inicio() -> str:
    return """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="0;url=ipca.html"><title>Inflação para gestores</title>
<p>Explore a implementação: <a href="ipca.html">IPCA geral</a> ou
<a href="ipca15.html">IPCA-15</a>.
As páginas funcionam também sem conexão após baixadas.</p></html>"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indice", choices=["ipca", "ipca15"])
    parser.add_argument("--verificar", action="store_true")
    args = parser.parse_args(argv)
    pasta = RAIZ / "docs" / "gestao"
    paginas = {f"{c}.html": gerar(c) for c in ([args.indice] if args.indice else CODIGOS_INDICES)}
    paginas["index.html"] = gerar_inicio()
    if args.verificar:
        atrasadas = [
            n
            for n, h in paginas.items()
            if not (pasta / n).exists() or (pasta / n).read_text() != h
        ]
        if atrasadas:
            print("Explicações desatualizadas: " + ", ".join(atrasadas))
            return 1
        return 0
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, html in paginas.items():
        (pasta / nome).write_text(html)
        print(f"docs/gestao/{nome} gerada")
    return 0


CODIGOS_INDICES = ("ipca", "ipca15")

if __name__ == "__main__":
    raise SystemExit(main())
