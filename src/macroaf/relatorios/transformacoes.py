"""Página HTML que explica as transformações de um índice, da API do IBGE ao staging.

Segue a escada de explicação do projeto: texto claro (resumo), diagramas (fluxo e linha do tempo)
e página interativa (etapas clicáveis, rastreio de um valor, visão executiva ou técnica). Todos os
números vêm de `coleta.coletar`; o texto fixo descreve o código e muda junto com ele.

Uso:

    uv run python -m macroaf.relatorios.transformacoes            # grava docs/transformacoes/ipca15.html
    uv run python -m macroaf.relatorios.transformacoes --verificar  # falha se a página estiver velha
"""

from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path

from macroaf.catalogo import RAIZ, carregar_catalogo
from macroaf.relatorios.coleta import coletar

NOMES_MEDIDA = {
    "variacao_mensal": "Variação mensal",
    "variacao_acum_ano": "Acumulada no ano",
    "variacao_acum_12m": "Acumulada em 12 meses",
    "peso": "Peso",
}

# Dúvidas que o projeto ainda não resolveu. Cada uma cita onde está registrada; ao resolver, a
# resposta vai para a fonte citada e a linha sai daqui.
DUVIDAS = [
    (
        "A cesta variável dos itens in natura da POF 1995-96 ainda não foi confirmada na "
        "documentação do IBGE; a conclusão se apoia só nos dados.",
        "METODOLOGIA.md 6.2 · A-013",
    ),
    (
        "Quais das 87 categorias com id novo continuam a mesma série (renomeada) e quais são "
        "quebra de série.",
        "issue #6 · A-012",
    ),
    (
        "Se o projeto reporta ao IBGE os erros publicados que encontrou, em especial os da 3065.",
        "METODOLOGIA.md 6.4 · A-015",
    ),
    (
        "Como o projeto absorve a próxima troca de POF (tabela nova no lugar da 7062).",
        "issue #27",
    ),
]


def caminho_pagina(codigo_indice: str) -> Path:
    return RAIZ / "docs" / "transformacoes" / f"{codigo_indice}.html"


def _n(valor: float | int) -> str:
    """Número no formato brasileiro (ponto no milhar, vírgula decimal)."""
    if isinstance(valor, int):
        return f"{valor:,}".replace(",", ".")
    return f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _mes(periodo: str) -> str:
    nomes = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    return f"{nomes[int(periodo[5:]) - 1]}/{periodo[:4]}"


def _etapas(f: dict) -> list[dict]:
    """As etapas do pipeline. O texto descreve o código; os números vêm da coleta."""
    dados = [t for t in f["tabelas"] if t["papel"] == "dados"]
    ref = next(t for t in f["tabelas"] if t["papel"] == "referencia")
    ok = sum(v["ok"] for v in f["validacoes"])
    return [
        {
            "id": "api",
            "titulo": "API do IBGE",
            "executiva": "O IBGE publica o IPCA-15 no SIDRA. O projeto lê só a API oficial, sem planilhas.",
            "entrada": "Tabelas "
            + ", ".join(str(t["tabela"]) for t in f["tabelas"])
            + " no SIDRA.",
            "regra": "Antes de baixar, confere se o período de cada tabela nos metadados bate com o catálogo. Divergência interrompe tudo.",
            "saida": "Respostas JSON, uma por tabela e mês, com todas as variáveis e categorias.",
            "comando": "uv run python -m macroaf.extract.atualizar",
            "codigo": "src/macroaf/extract/",
            "numeros": [
                ("Tabelas no catálogo", _n(len(f["tabelas"]))),
                ("Limite da API por consulta", "50.000 valores"),
            ],
        },
        {
            "id": "raw",
            "titulo": "Camada raw",
            "executiva": "Guarda exatamente o que o IBGE respondeu, compactado. Nada é editado nem apagado.",
            "entrada": "Corpo de cada resposta da API.",
            "regra": "Baixa só os meses que faltam. Nas tabelas abertas, baixa de novo os 3 últimos meses e guarda uma revisão ao lado se o IBGE mudou algo.",
            "saida": "data/raw/ibge_sidra/<tabela>/<AAAAMM>.json.gz, metadados.json.gz e manifesto.csv com o hash de cada arquivo.",
            "comando": "uv run python -m macroaf.extract.atualizar",
            "codigo": "src/macroaf/extract/raw.py",
            "numeros": [
                ("Arquivos", _n(f["raw"]["arquivos"])),
                ("Registros", _n(f["raw"]["registros"])),
                (
                    "Tamanho",
                    f"{_n(f['raw']['megabytes_gzip'])} MB (de {_n(f['raw']['megabytes_json'])} MB em JSON)",
                ),
                ("Revisões do IBGE guardadas", _n(f["raw"]["revisoes"])),
            ],
        },
        {
            "id": "dim",
            "titulo": "dim_classificacao",
            "executiva": "Lista todas as categorias de cada tabela (geral, grupos, subgrupos, itens e subitens) com a sua posição na árvore.",
            "entrada": "metadados.json.gz de cada tabela de dados (classificação "
            + str(f["indice"]["classificacao"])
            + ").",
            "regra": "O nível sai do número de dígitos do código no nome (1, 2, 4 ou 7). O campo nivel da API não é usado. O índice geral recebe o código 0.",
            "saida": "Uma linha por categoria e tabela: código IBGE, id SIDRA, nome, nível, pai, grupo, subgrupo e item.",
            "comando": "uv run python -m macroaf.transform.ipca15",
            "codigo": "src/macroaf/transform/classificacao.py",
            "numeros": [
                ("Categorias (todas as tabelas)", _n(f["dim"]["linhas"])),
                ("Códigos com id SIDRA diferente entre tabelas", _n(f["dim"]["trocas_de_id"])),
            ],
        },
        {
            "id": "fato",
            "titulo": "fato_" + f["indice"]["codigo"],
            "executiva": "Junta os valores de todas as tabelas num só lugar: uma linha por mês e categoria, com as medidas em colunas.",
            "entrada": "Arquivos de valores do raw das tabelas "
            + ", ".join(str(t["tabela"]) for t in dados)
            + " e a dim_classificacao.",
            "regra": "Cada valor é ligado à categoria pelo par (tabela, id SIDRA), nunca só pelo código IBGE. O texto ... vira ausente, nunca zero. Outro texto não numérico para a transformação.",
            "saida": "Colunas: " + ", ".join(f["fato"]["colunas"]) + ".",
            "comando": "uv run python -m macroaf.transform.ipca15",
            "codigo": "src/macroaf/transform/ipca15.py",
            "numeros": [
                ("Linhas", _n(f["fato"]["linhas"])),
                ("Período", f"{_mes(f['periodo']['inicio'])} a {_mes(f['periodo']['fim'])}"),
            ],
        },
        {
            "id": "ref",
            "titulo": "ref_" + f["indice"]["codigo"] + "_geral",
            "executiva": "Guarda a série oficial do índice geral, usada como gabarito para conferir o resto.",
            "entrada": f"Arquivos de valores do raw da tabela {ref['tabela']}.",
            "regra": "Só reorganiza: uma linha por mês, variáveis em colunas.",
            "saida": "Colunas: " + ", ".join(f["referencia"]["colunas"]) + ".",
            "comando": "uv run python -m macroaf.transform.ipca15",
            "codigo": "src/macroaf/transform/ipca15.py",
            "numeros": [("Meses", _n(f["referencia"]["meses"]))],
        },
        {
            "id": "validacoes",
            "titulo": "Validações",
            "executiva": "Conferem se os dados fecham: pesos somam 100, filhos explicam o pai, acumulados batem e o geral reproduz a referência.",
            "entrada": "fato, referência, catálogo e as listas de exceções e limites em reference/.",
            "regra": "Cada diferença é comparada com o maior erro que o arredondamento do IBGE pode produzir. Acima disso, só passa se houver exceção documentada, e cada exceção cobre um número exato de casos.",
            "saida": "Relatório validacao.json. Uma falha bloqueia a publicação.",
            "comando": "uv run python -m macroaf.validate.ipca15",
            "codigo": "src/macroaf/validate/ipca15.py",
            "numeros": [
                ("Validações ok", f"{ok} de {len(f['validacoes'])}"),
                ("Exceções documentadas", _n(len(f["excecoes"]))),
                ("Sentinelas alteradas", _n(f["sentinelas"])),
            ],
        },
        {
            "id": "marts",
            "titulo": "Marts (a fazer)",
            "executiva": "Tabelas finais para o Power BI e o site. Ainda não existem.",
            "entrada": "fato, série longa harmonizada (#6) e indicadores (#7).",
            "regra": "Nomes de arquivo estáveis, porque o Power BI lê pelas URLs do GitHub.",
            "saida": "data/marts/*.parquet e *.csv, dicionário de dados e metadata.json (#8).",
            "comando": "ainda não existe",
            "codigo": "issue #8",
            "numeros": [("Arquivos hoje", _n(len(f["marts"])))],
        },
    ]


def _svg_fluxo(f: dict) -> str:
    """Fluxo raw → staging: cada caixa é clicável e abre a etapa."""
    caixa = 'class="no" data-etapa="{id}" tabindex="0" role="button" aria-label="{rotulo}"'

    def no(id_, x, y, w, titulo, sub, pendente=False):
        classe = " pendente" if pendente else ""
        return (
            f"<g {caixa.format(id=id_, rotulo=escape(titulo))}>"
            f'<rect class="caixa{classe}" x="{x}" y="{y}" width="{w}" height="58" rx="6"/>'
            f'<text class="t1" x="{x + w / 2}" y="{y + 25}" text-anchor="middle">{escape(titulo)}</text>'
            f'<text class="t2" x="{x + w / 2}" y="{y + 44}" text-anchor="middle">{escape(sub)}</text></g>'
        )

    def seta(x1, y1, x2, y2, rotulo="", pendente=False):
        classe = "seta pendente" if pendente else "seta"
        texto = (
            f'<text class="t3" x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 - 6}" text-anchor="middle">{escape(rotulo)}</text>'
            if rotulo
            else ""
        )
        return f'<line class="{classe}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" marker-end="url(#ponta)"/>{texto}'

    raw = f["raw"]
    partes = [
        no("api", 10, 121, 120, "API do IBGE", "SIDRA"),
        no("raw", 190, 121, 140, "raw", f"{_n(raw['arquivos'])} arquivos"),
        no("dim", 420, 21, 170, "dim_classificacao", f"{_n(f['dim']['linhas'])} categorias"),
        no(
            "fato",
            420,
            121,
            170,
            "fato_" + f["indice"]["codigo"],
            f"{_n(f['fato']['linhas'])} linhas",
        ),
        no("ref", 420, 221, 170, "ref_geral", f"{_n(f['referencia']['meses'])} meses"),
        no(
            "validacoes", 670, 121, 140, "validações", f"{sum(v['ok'] for v in f['validacoes'])} ok"
        ),
        no("marts", 870, 121, 120, "marts", "a fazer", pendente=True),
        seta(130, 150, 186, 150, "baixa"),
        seta(330, 140, 416, 55, "metadados"),
        seta(330, 150, 416, 150, "valores"),
        seta(330, 160, 416, 245, "3065"),
        seta(505, 79, 505, 117, "par tabela+id"),
        seta(590, 150, 666, 150),
        seta(590, 245, 666, 165, "gabarito"),
        seta(810, 150, 866, 150, "#6 #7 #8", pendente=True),
    ]
    return (
        '<svg viewBox="0 0 1000 300" role="img" aria-label="Fluxo dos dados: a API do IBGE alimenta '
        "a camada raw; os metadados viram a dim_classificacao, os valores viram o fato (ligado à dim "
        "pelo par tabela e id) e a tabela 3065 vira a referência; as validações conferem fato e "
        'referência; os marts ainda não existem.">'
        '<defs><marker id="ponta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="ponta"/></marker></defs>'
        + "".join(partes)
        + "</svg>"
    )


def _svg_linha_do_tempo(f: dict) -> str:
    """Tabelas no tempo, com as trocas de POF marcadas."""
    inicio_ano, fim_ano = int(f["periodo"]["inicio"][:4]), int(f["periodo"]["fim"][:4]) + 1
    x0, x1 = 120, 980

    def x(periodo: str) -> float:
        meses = (int(periodo[:4]) - inicio_ano) * 12 + int(periodo[5:]) - 1
        return x0 + (x1 - x0) * meses / ((fim_ano - inicio_ano) * 12)

    partes = []
    for ano in range(inicio_ano, fim_ano + 1, 2):
        xa = x(f"{ano}-01")
        partes.append(f'<line class="grade" x1="{xa:.1f}" y1="20" x2="{xa:.1f}" y2="196"/>')
        partes.append(f'<text class="t3" x="{xa:.1f}" y="214" text-anchor="middle">{ano}</text>')
    for linha, t in enumerate(f["tabelas"]):
        y = 30 + linha * 34
        classe = "barra-ref" if t["papel"] == "referencia" else f"barra pof{linha}"
        fim = t["fim"]
        largura = x(fim) - x(t["inicio"]) + (x1 - x0) / ((fim_ano - inicio_ano) * 12)
        rotulo = f"POF {t['versao_pof']}" if t["versao_pof"] else "referência (só o geral)"
        partes.append(f'<text class="t1" x="10" y="{y + 15}">{t["tabela"]}</text>')
        partes.append(
            f'<rect class="{classe}" x="{x(t["inicio"]):.1f}" y="{y}" width="{largura:.1f}" height="22" rx="3"/>'
        )
        partes.append(
            f'<text class="t2 dentro" x="{x(t["inicio"]) + 6:.1f}" y="{y + 15}">{escape(rotulo)}</text>'
        )
        if t["papel"] == "dados" and linha > 0:
            partes.append(
                f'<line class="troca" x1="{x(t["inicio"]):.1f}" y1="20" x2="{x(t["inicio"]):.1f}" y2="196"/>'
            )
            partes.append(
                f'<text class="t3 troca-t" x="{x(t["inicio"]) + 4:.1f}" y="{18}">{_mes(t["inicio"])}</text>'
            )
    return (
        f'<svg viewBox="0 0 1000 224" role="img" aria-label="Linha do tempo: quatro tabelas de dados se '
        f"sucedem sem lacuna, uma por estrutura de pesos (POF), e a tabela de referência cobre de "
        f'{_mes(f["periodo"]["inicio"])} a {_mes(f["periodo"]["fim"])}.">'
        + "".join(partes)
        + "</svg>"
    )


def _tabela_html(cabecalho: list[str], linhas: list[list[str]], classe: str = "") -> str:
    th = "".join(f"<th>{c}</th>" for c in cabecalho)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in linha) + "</tr>" for linha in linhas)
    return f'<div class="rolagem"><table class="{classe}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def _existe(f: dict) -> str:
    dados = [t for t in f["tabelas"] if t["papel"] == "dados"]
    linhas = []
    for coluna, nome in NOMES_MEDIDA.items():
        celulas = []
        for t in dados:
            cobertura = t["cobertura"][coluna]
            if cobertura == 100:
                celulas.append('<span class="selo sim">oficial, 100%</span>')
            elif cobertura:
                celulas.append(f'<span class="selo parcial">oficial, {_n(cobertura)}%</span>')
            else:
                celulas.append('<span class="selo nao">não publicado</span>')
        linhas.append([nome, *celulas, '<span class="selo nao">não</span>'])
    oficial_geral = [
        ("Número-índice do geral", "numero_indice"),
        ("Acumulada em 3 meses do geral", "variacao_acum_3m"),
        ("Acumulada em 6 meses do geral", "variacao_acum_6m"),
    ]
    for nome, coluna in oficial_geral:
        if coluna in f["referencia"]["colunas"]:
            linhas.append(
                [
                    nome,
                    *['<span class="selo sim">pela 3065</span>'] * len(dados),
                    '<span class="selo nao">não</span>',
                ]
            )
    cabecalho = [
        "Medida",
        *[f"{t['tabela']}<br><small>POF {t['versao_pof']}</small>" for t in dados],
        "Calculada pelo projeto",
    ]
    return _tabela_html(cabecalho, linhas, "matriz")


def _secao_resumo(f: dict) -> str:
    dados = [t for t in f["tabelas"] if t["papel"] == "dados"]
    ok = sum(v["ok"] for v in f["validacoes"])
    feito = [
        f"Baixamos da API do IBGE {_n(f['raw']['arquivos'])} respostas ({_n(f['raw']['registros'])} valores), de {_mes(f['periodo']['inicio'])} a {_mes(f['periodo']['fim'])}, e guardamos como vieram.",
        f"Montamos a lista de categorias das {len(dados)} tabelas ({_n(f['dim']['linhas'])} linhas), com a hierarquia tirada do código IBGE.",
        f"Juntamos os valores das {len(dados)} tabelas num só fato ({_n(f['fato']['linhas'])} linhas), ligados à categoria certa pelo par tabela e id.",
        f"Conferimos tudo com {len(f['validacoes'])} validações ({ok} ok) e documentamos {len(f['excecoes'])} exceções explicadas.",
        "Ainda não calculamos nenhuma inflação: todos os números do fato são oficiais. Os cálculos feitos até agora servem só para conferir.",
    ]
    quem = [
        ("macroaf.extract", "baixa e guarda o raw"),
        ("macroaf.transform", "monta dim, fato e referência"),
        ("macroaf.validate", "confere e bloqueia a publicação se algo não fecha"),
        *[(a["nome"], a["descricao"].split(". ")[0] + ".") for a in f["agentes"]],
        ("mantenedor", "revisa e aprova cada PR, decisão e regra"),
    ]
    lista = lambda itens: "".join(f"<li>{escape(i)}</li>" for i in itens)  # noqa: E731
    return f"""
<section id="resumo" class="secao">
  <h2>Em resumo</h2>
  <div class="grade4">
    <div class="bloco"><h3>O que foi feito</h3><ul>{lista(feito)}</ul></div>
    <div class="bloco"><h3>Quem faz o quê</h3><dl class="pares">{"".join(f"<dt><code>{escape(n)}</code></dt><dd>{escape(d)}</dd>" for n, d in quem)}</dl></div>
    <div class="bloco"><h3>Decisões tomadas</h3><ul>{"".join(f"<li><b>{escape(d['tema'])}:</b> {escape(d['decisao'])}</li>" for d in f["decisoes"])}</ul></div>
    <div class="bloco alerta"><h3>Dúvidas em aberto</h3><ul>{"".join(f"<li>{escape(t)} <small>({escape(o)})</small></li>" for t, o in DUVIDAS)}</ul></div>
  </div>
</section>"""


def _secao_juncao(f: dict) -> str:
    exemplos = []
    for e in f["dim"]["exemplos_id"]:
        versoes = " → ".join(
            f'<span class="versao"><b>{v["tabela_sidra"]}</b> id {v["codigo_sidra"]} · {escape(v["nome"])}</span>'
            for v in e["versoes"]
        )
        exemplos.append([f"<code>{e['codigo_ibge']}</code>", versoes])
    botoes = "".join(
        f'<button type="button" class="aba" data-rastreio="{i}" id="rastreio-{r["tabela"]}">{r["tabela"]} · {_mes(r["mes"])}</button>'
        for i, r in enumerate(f["rastreios"])
    )
    niveis = ", ".join(f"{n} {k}" for k, n in f["dim"]["trocas_por_nivel"].items())
    return f"""
<section id="juncao" class="secao">
  <h2>Como as tabelas se juntam</h2>
  <p>Cada categoria tem dois identificadores. O <b>código IBGE</b> (ex.: <code>1111004</code>) diz a posição na árvore. O <b>id SIDRA</b> (ex.: <code>12393</code>) diz qual definição da categoria vale naquela tabela. Quando o IBGE reformula uma categoria, mantém o código e cria um id novo. Isso aconteceu em <b>{_n(f["dim"]["trocas_de_id"])}</b> códigos ({escape(niveis)}).</p>
  <p>Por isso o fato liga cada valor à categoria pelo par <b>(tabela, id SIDRA)</b>. Ligar só pelo código misturaria produtos diferentes, como mostram os exemplos.</p>
  {_tabela_html(["Código IBGE", "Versões ao longo das tabelas"], exemplos)}
  <h3>Rastreie um valor</h3>
  <p>O mesmo subitem (<code>1111004</code>) no último mês de cada tabela: o registro como veio da API, a linha da classificação e a linha final no fato.</p>
  <div class="abas" role="group" aria-label="Escolha a tabela">{botoes}</div>
  <div id="rastreio" class="rastreio" aria-live="polite"></div>
</section>"""


def _secao_existe(f: dict) -> str:
    planejados = [
        [
            escape(i["indicador"]),
            escape(i["definicao"]),
            escape(i["teste"]),
            '<span class="selo nao">a fazer (#7)</span>',
        ]
        for i in f["indicadores_planejados"]
    ]
    return f"""
<section id="existe" class="secao">
  <h2>O que já existe e o que não existe</h2>
  <p>As medidas abaixo estão no fato <b>como o IBGE publica</b>, para todos os níveis (geral, grupo, subgrupo, item e subitem). A porcentagem é a parte das linhas da tabela que tem valor.</p>
  {_existe(f)}
  <ul class="notas">
    <li>O acumulado em 12 meses não existe nas tabelas 1646 e 1387 e vem vazio em parte da 1705 e da 7062 (A-009). Calcular onde falta é tarefa da #7.</li>
    <li>Agregação: o projeto não agrega nada que guarde. As validações recalculam médias ponderadas, acumulados e o número-índice só para conferir com o IBGE.</li>
    <li>Série longa: as quatro tabelas estão lado a lado, cada uma com a sua POF. Emendar abaixo do subgrupo depende da harmonização (#6).</li>
  </ul>
  <h3>Indicadores planejados</h3>
  {_tabela_html(["Indicador", "Definição", "Teste previsto", "Situação"], planejados)}
  <p>Marts publicados para o Power BI e o site: <b>{_n(len(f["marts"]))}</b> (#8).</p>
</section>"""


def _secao_validacoes(f: dict) -> str:
    linhas = []
    for v in f["validacoes"]:
        selo = (
            '<span class="selo sim">ok</span>'
            if v["ok"]
            else '<span class="selo falha">falha</span>'
        )
        linhas.append(
            [
                f"<code>{v['validacao']}</code>",
                selo,
                _n(v["verificados"]),
                _n(v["excecoes_aplicadas"]),
                escape(v["limite"]),
            ]
        )
    excecoes = [
        [
            f'<span class="selo {"estrutural" if e["tipo"] == "estrutural" else "fonte"}">{e["tipo"]}</span>',
            f"<code>{e['validacao']}</code>",
            str(e["tabela_sidra"]),
            f"<code>{escape(e['codigo_ibge'])}</code>",
            f"{e['mes_inicio']} a {e['mes_fim']}",
            _n(int(e["falhas_cobertas"])),
            escape(e["justificativa"]),
            e["aprendizado"],
        ]
        for e in f["excecoes"]
    ]
    return f"""
<section id="validacoes" class="secao">
  <h2>Validações</h2>
  <p>Toda execução roda estas conferências. O limite de cada uma é o maior erro que o arredondamento do IBGE (2 casas nas variações, 4 nos pesos) pode produzir, salvo onde está indicado. Uma falha, ou uma exceção que passe a cobrir mais ou menos casos do que o registrado, bloqueia a publicação.</p>
  {_tabela_html(["Validação", "Situação", "Verificados", "Cobertos por exceção", "Limite"], linhas)}
  <h3>Exceções documentadas</h3>
  <p><b>Estrutural</b>: o método do IBGE era diferente (ex.: cesta variável). <b>Fonte</b>: erro publicado pelo IBGE, conferido na API e mantido como está.</p>
  <div class="abas" role="group" aria-label="Filtrar exceções">
    <button type="button" class="aba ativa" data-filtro="todas" id="filtro-todas">Todas</button>
    <button type="button" class="aba" data-filtro="estrutural" id="filtro-estrutural">Estruturais</button>
    <button type="button" class="aba" data-filtro="fonte" id="filtro-fonte">Da fonte</button>
  </div>
  {_tabela_html(["Tipo", "Validação", "Tabela", "Código", "Meses", "Casos", "Justificativa", "Lição"], excecoes, "excecoes")}
</section>"""


def _secao_descobertas(f: dict) -> str:
    itens = "".join(
        f'<li><span class="cod">{a["codigo"]}</span> {escape(a["titulo"])}</li>'
        for a in f["aprendizados"]
    )
    return f"""
<section id="descobertas" class="secao">
  <h2>Descobertas registradas</h2>
  <p>Cada descoberta está em <code>docs/aprendizados.md</code> (como foi encontrada) e, quando muda o tratamento dos dados, em <code>docs/METODOLOGIA.md</code> (a regra que o projeto segue).</p>
  <ol class="descobertas" reversed>{itens}</ol>
</section>"""


def _secao_manter(f: dict) -> str:
    codigo = f["indice"]["codigo"]
    return f"""
<section id="manter" class="secao">
  <h2>Como manter esta página certa</h2>
  <p>Esta página é gerada pelo código a partir dos dados do repositório. Ninguém a edita à mão. Para atualizar:</p>
  <pre><code>uv run python -m macroaf.extract.atualizar
uv run python -m macroaf.transform.{codigo}
uv run python -m macroaf.validate.{codigo}
uv run python -m macroaf.relatorios.transformacoes --indice {codigo}</code></pre>
  <p>Um teste regera a página e falha se o arquivo do repositório estiver diferente. Toda etapa que muda uma transformação regera a página no mesmo PR. Um índice novo ganha a sua página com <code>--indice</code>.</p>
  <p class="tecnico">Degraus de explicação usados aqui: texto claro (resumo), diagramas (fluxo e linha do tempo) e página interativa. O degrau de vídeo ainda não foi feito.</p>
</section>"""


CSS = """
/* Documento técnico de leitura longa: coluna larga para tabelas, tipografia de relatório estatístico. */
:root {
  --papel: #f6f7f9; --superficie: #ffffff; --tinta: #17202b; --suave: #556170; --linha: #d5dbe3;
  --destaque: #1d5b8f; --destaque-fundo: #e3eef8; --pof0: #9fbfdc; --pof1: #7fb2a9; --pof2: #c9b37a; --pof3: #b394c2;
  --sim: #2e7d4f; --sim-fundo: #e4f3ea; --parcial: #8a6100; --parcial-fundo: #fbf0d6; --nao: #8b95a3; --nao-fundo: #eef1f4;
  --falha: #b3261e; --falha-fundo: #fbe4e2; --alerta-fundo: #fff7e6;
  --fonte-titulo: "IBM Plex Sans Condensed", "Arial Narrow", system-ui, sans-serif;
  --fonte-texto: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --fonte-dados: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --papel: #11161d; --superficie: #19202a; --tinta: #e6eaf0; --suave: #9aa6b5; --linha: #2c3643;
  --destaque: #7db4e6; --destaque-fundo: #1b2e42; --pof0: #3d5f80; --pof1: #3b6b63; --pof2: #6e5f33; --pof3: #5d4a6b;
  --sim: #7dd3a0; --sim-fundo: #183528; --parcial: #e6c070; --parcial-fundo: #3a3018; --nao: #8b95a3; --nao-fundo: #222a35;
  --falha: #f2a49d; --falha-fundo: #3d1d1b; --alerta-fundo: #2e2717; color-scheme: dark; } }
:root[data-theme="dark"] {
  --papel: #11161d; --superficie: #19202a; --tinta: #e6eaf0; --suave: #9aa6b5; --linha: #2c3643;
  --destaque: #7db4e6; --destaque-fundo: #1b2e42; --pof0: #3d5f80; --pof1: #3b6b63; --pof2: #6e5f33; --pof3: #5d4a6b;
  --sim: #7dd3a0; --sim-fundo: #183528; --parcial: #e6c070; --parcial-fundo: #3a3018; --nao: #8b95a3; --nao-fundo: #222a35;
  --falha: #f2a49d; --falha-fundo: #3d1d1b; --alerta-fundo: #2e2717; color-scheme: dark; }
body { background: var(--papel); color: var(--tinta); font-family: var(--fonte-texto); font-size: 15px; line-height: 1.55; }
.pagina { max-width: 1120px; margin: 0 auto; padding-block: 28px 64px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 40px; }
h1, h2, h3 { font-family: var(--fonte-titulo); text-wrap: balance; line-height: 1.15; margin: 0; }
h1 { font-size: 2.2rem; font-weight: 600; }
h2 { font-size: 1.5rem; font-weight: 600; border-bottom: 2px solid var(--tinta); padding-bottom: 6px; }
h3 { font-size: 1.1rem; font-weight: 600; }
p { margin: 0; max-width: 72ch; }
code, pre, .cod { font-family: var(--fonte-dados); font-size: 0.86em; }
small { color: var(--suave); }
.secao { display: grid; gap: 16px; min-width: 0; }
.topo { display: grid; gap: 12px; }
.olho { font-family: var(--fonte-dados); font-size: 0.8rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--destaque); }
.fatos { display: flex; flex-wrap: wrap; gap: 8px 24px; color: var(--suave); font-variant-numeric: tabular-nums; }
.fatos b { color: var(--tinta); }
.controles { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
nav.indice { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 0.92rem; }
nav.indice a { color: var(--destaque); text-decoration: none; }
nav.indice a:hover, nav.indice a:focus-visible { text-decoration: underline; }
.grade4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
.bloco { background: var(--superficie); border: 1px solid var(--linha); border-radius: 6px; padding: 16px; display: grid; gap: 8px; align-content: start; min-width: 0; }
.bloco.alerta { background: var(--alerta-fundo); }
.bloco ul { margin: 0; padding-left: 18px; display: grid; gap: 6px; }
dl.pares { margin: 0; display: grid; gap: 2px; font-size: 0.92rem; }
dl.pares dt { margin: 6px 0 0; } dl.pares dt:first-child { margin-top: 0; } dl.pares dd { margin: 0; color: var(--suave); }
figure { margin: 0; display: grid; gap: 8px; min-width: 0; }
figcaption { color: var(--suave); font-size: 0.9rem; max-width: 72ch; }
.rolagem { overflow-x: auto; min-width: 0; }
svg { width: 100%; height: auto; display: block; min-width: 640px; }
svg text { fill: var(--tinta); font-family: var(--fonte-texto); }
svg .t1 { font-size: 14px; font-weight: 600; } svg .t2 { font-size: 12px; fill: var(--suave); } svg .t3 { font-size: 11px; fill: var(--suave); }
svg .caixa { fill: var(--superficie); stroke: var(--tinta); stroke-width: 1.4; }
svg .caixa.pendente { stroke-dasharray: 5 4; fill: var(--papel); }
svg .no { cursor: pointer; } svg .no:hover .caixa, svg .no:focus-visible .caixa, svg .no.ativo .caixa { fill: var(--destaque-fundo); stroke: var(--destaque); stroke-width: 2.2; }
svg .no:focus { outline: none; }
svg .seta { stroke: var(--tinta); stroke-width: 1.4; } svg .seta.pendente { stroke-dasharray: 5 4; stroke: var(--suave); }
svg .ponta { fill: var(--tinta); }
svg .grade { stroke: var(--linha); stroke-width: 1; }
svg .barra.pof0 { fill: var(--pof0); } svg .barra.pof1 { fill: var(--pof1); } svg .barra.pof2 { fill: var(--pof2); } svg .barra.pof3 { fill: var(--pof3); }
svg .barra-ref { fill: none; stroke: var(--tinta); stroke-width: 1.4; stroke-dasharray: 4 3; }
svg .dentro { fill: var(--tinta); }
svg .troca { stroke: var(--destaque); stroke-width: 1.6; stroke-dasharray: 2 3; } svg .troca-t { fill: var(--destaque); font-weight: 600; }
.detalhe { background: var(--superficie); border: 1px solid var(--linha); border-left: 4px solid var(--destaque); border-radius: 6px; padding: 16px; display: grid; gap: 10px; min-width: 0; }
.detalhe dl { margin: 0; display: grid; grid-template-columns: minmax(90px, max-content) 1fr; gap: 6px 14px; }
.detalhe dt { color: var(--suave); } .detalhe dd { margin: 0; min-width: 0; overflow-wrap: anywhere; }
.numeros { display: flex; flex-wrap: wrap; gap: 8px 20px; font-variant-numeric: tabular-nums; }
.numeros div { display: grid; } .numeros span { color: var(--suave); font-size: 0.82rem; } .numeros b { font-size: 1.05rem; }
.abas { display: flex; flex-wrap: wrap; gap: 6px; }
button.aba { font: inherit; font-size: 0.9rem; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--linha); background: var(--superficie); color: var(--tinta); cursor: pointer; }
button.aba:hover { border-color: var(--destaque); }
button.aba.ativa, button.aba[aria-pressed="true"] { background: var(--destaque); border-color: var(--destaque); color: var(--papel); }
button:focus-visible, a:focus-visible { outline: 2px solid var(--destaque); outline-offset: 2px; }
table { border-collapse: collapse; width: 100%; font-size: 0.9rem; font-variant-numeric: tabular-nums; background: var(--superficie); }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--linha); vertical-align: top; }
th { font-family: var(--fonte-titulo); font-weight: 600; background: var(--papel); position: sticky; top: 0; }
table.excecoes td:nth-child(7) { min-width: 260px; }
.versao { display: inline-block; white-space: nowrap; }
.selo { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 0.8rem; white-space: nowrap; }
.selo.sim { background: var(--sim-fundo); color: var(--sim); } .selo.parcial { background: var(--parcial-fundo); color: var(--parcial); }
.selo.nao { background: var(--nao-fundo); color: var(--nao); } .selo.falha { background: var(--falha-fundo); color: var(--falha); }
.selo.estrutural { background: var(--destaque-fundo); color: var(--destaque); } .selo.fonte { background: var(--parcial-fundo); color: var(--parcial); }
.rastreio { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
.rastreio .bloco pre { margin: 0; overflow-x: auto; font-size: 0.78rem; line-height: 1.45; }
.notas { margin: 0; padding-left: 18px; display: grid; gap: 6px; color: var(--suave); max-width: 80ch; }
ol.descobertas { margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; }
ol.descobertas .cod { display: inline-block; min-width: 4.2em; color: var(--destaque); font-weight: 600; }
pre { background: var(--superficie); border: 1px solid var(--linha); border-radius: 6px; padding: 12px; overflow-x: auto; margin: 0; }
body.executiva .tecnico { display: none; }
@media (prefers-reduced-motion: no-preference) { button.aba, svg .caixa { transition: background 0.15s, fill 0.15s, stroke 0.15s; } }
"""

JS = """
const dados = JSON.parse(document.getElementById('dados').textContent);
const etapas = Object.fromEntries(dados.etapas.map((e) => [e.id, e]));
const painel = document.getElementById('detalhe');
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

function mostrarEtapa(id) {
  const e = etapas[id];
  document.querySelectorAll('svg .no').forEach((n) => n.classList.toggle('ativo', n.dataset.etapa === id));
  painel.innerHTML = `<h3>${esc(e.titulo)}</h3><p>${esc(e.executiva)}</p>
    <div class="numeros">${e.numeros.map(([r, v]) => `<div><span>${esc(r)}</span><b>${esc(v)}</b></div>`).join('')}</div>
    <dl class="tecnico"><dt>Entrada</dt><dd>${esc(e.entrada)}</dd><dt>Regra</dt><dd>${esc(e.regra)}</dd>
    <dt>Saída</dt><dd>${esc(e.saida)}</dd><dt>Comando</dt><dd><code>${esc(e.comando)}</code></dd>
    <dt>Código</dt><dd><code>${esc(e.codigo)}</code></dd></dl>`;
}
document.querySelectorAll('svg .no').forEach((n) => {
  n.addEventListener('click', () => mostrarEtapa(n.dataset.etapa));
  n.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); mostrarEtapa(n.dataset.etapa); } });
});
mostrarEtapa('fato');

const json = (o) => esc(JSON.stringify(o, null, 2));
function mostrarRastreio(i) {
  const r = dados.rastreios[i];
  document.querySelectorAll('[data-rastreio]').forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.rastreio) === i)));
  document.getElementById('rastreio').innerHTML = `
    <div class="bloco"><h3>1. Como veio da API</h3><small><code>${esc(r.arquivo)}</code>: ${r.raw.length} registros, um por variável</small><pre>${json(r.raw)}</pre></div>
    <div class="bloco"><h3>2. dim_classificacao</h3><small>linha da tabela ${r.tabela} com id ${r.dim.codigo_sidra}</small><pre>${json(r.dim)}</pre></div>
    <div class="bloco"><h3>3. fato</h3><small>uma linha, variáveis em colunas; null = não publicado</small><pre>${json(r.fato)}</pre></div>`;
}
document.querySelectorAll('[data-rastreio]').forEach((b) => b.addEventListener('click', () => mostrarRastreio(Number(b.dataset.rastreio))));
mostrarRastreio(dados.rastreios.length - 1);

document.querySelectorAll('[data-filtro]').forEach((b) => b.addEventListener('click', () => {
  document.querySelectorAll('[data-filtro]').forEach((o) => o.classList.toggle('ativa', o === b));
  document.querySelectorAll('table.excecoes tbody tr').forEach((tr) => {
    tr.hidden = b.dataset.filtro !== 'todas' && !tr.querySelector('.selo.' + b.dataset.filtro);
  });
}));

const botoesVisao = document.querySelectorAll('[data-visao]');
function definirVisao(v) {
  document.body.classList.toggle('executiva', v === 'executiva');
  botoesVisao.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.visao === v)));
  try { localStorage.setItem('visao', v); } catch (e) { /* armazenamento indisponível */ }
}
botoesVisao.forEach((b) => b.addEventListener('click', () => definirVisao(b.dataset.visao)));
let inicial = 'tecnica';
try { inicial = localStorage.getItem('visao') || 'tecnica'; } catch (e) { /* armazenamento indisponível */ }
definirVisao(inicial);
"""


def renderizar(f: dict) -> str:
    etapas = _etapas(f)
    nome = f["indice"]["nome"]
    dados_js = json.dumps(
        {"etapas": etapas, "rastreios": f["rastreios"]}, ensure_ascii=False, default=str
    )
    dados_js = dados_js.replace("</", "<\\/")
    ok = sum(v["ok"] for v in f["validacoes"])
    tabelas_dados = [t for t in f["tabelas"] if t["papel"] == "dados"]
    return f"""<title>Transformações do {escape(nome)}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Sans:ital,wght@0,400;0,600;1,400&display=swap">
<style>{CSS}</style>
<main class="pagina">
  <header class="topo">
    <span class="olho">Macroeconomia da Agricultura Familiar · {escape(f["indice"]["codigo"])}</span>
    <h1>Transformações do {escape(nome)}</h1>
    <p>Do que o IBGE publica até as tabelas do projeto: o que foi feito em cada etapa, como as tabelas se juntam, o que já existe e o que falta. Tudo nesta página foi gerado a partir dos dados e do código do repositório.</p>
    <div class="fatos">
      <span><b>{_mes(f["periodo"]["inicio"])} a {_mes(f["periodo"]["fim"])}</b> de dados</span>
      <span><b>{len(tabelas_dados)}</b> tabelas de dados, uma por POF</span>
      <span><b>{_n(f["fato"]["linhas"])}</b> linhas no fato</span>
      <span><b>{ok} de {len(f["validacoes"])}</b> validações ok</span>
    </div>
    <div class="controles">
      <span>Visão:</span>
      <button type="button" class="aba" data-visao="executiva" id="visao-executiva" aria-pressed="false">Executiva</button>
      <button type="button" class="aba" data-visao="tecnica" id="visao-tecnica" aria-pressed="true">Técnica</button>
    </div>
    <nav class="indice" aria-label="Seções">
      <a href="#resumo">Em resumo</a><a href="#fluxo">Caminho dos dados</a><a href="#tempo">Linha do tempo</a>
      <a href="#juncao">Como as tabelas se juntam</a><a href="#existe">O que existe</a>
      <a href="#validacoes">Validações</a><a href="#descobertas">Descobertas</a><a href="#manter">Manter atualizado</a>
    </nav>
  </header>
  {_secao_resumo(f)}
  <section id="fluxo" class="secao">
    <h2>O caminho dos dados</h2>
    <p>Clique numa etapa para ver o que entra, a regra aplicada, o que sai e o comando que a executa. A visão executiva esconde os detalhes técnicos.</p>
    <figure>
      <div class="rolagem">{_svg_fluxo(f)}</div>
      <figcaption>Os metadados viram a classificação, os valores viram o fato e a tabela 3065 vira o gabarito do índice geral. A caixa tracejada ainda não existe.</figcaption>
    </figure>
    <div id="detalhe" class="detalhe" aria-live="polite"></div>
  </section>
  <section id="tempo" class="secao">
    <h2>Linha do tempo das tabelas</h2>
    <p>O IBGE publica o {escape(nome)} numa tabela nova a cada troca da estrutura de pesos (POF). As tabelas de dados se sucedem mês a mês, sem lacuna. A tabela 3065 traz só o índice geral, do início ao fim, e serve de gabarito.</p>
    <figure>
      <div class="rolagem">{_svg_linha_do_tempo(f)}</div>
      <figcaption>As linhas verticais marcam as trocas de POF. A troca chega ao {escape(nome)} um mês depois de chegar ao IPCA (A-007).</figcaption>
    </figure>
    {_tabela_html(["Tabela", "Papel", "Período", "Variáveis", "Categorias (grupo / subgrupo / item / subitem)", "Meses no raw"], [[str(t["tabela"]), "dados" if t["papel"] == "dados" else "referência", f"{_mes(t['inicio'])} a {_mes(t['fim'])}" + (" (aberta)" if t["aberta"] else ""), ", ".join(f"{v['codigo']} {v['nome']}" for v in t["variaveis"]), " / ".join(str(t["categorias"][n]) for n in ["grupo", "subgrupo", "item", "subitem"]) if t["papel"] == "dados" else "só o geral", _n(t["meses_raw"])] for t in f["tabelas"]])}
  </section>
  {_secao_juncao(f)}
  {_secao_existe(f)}
  {_secao_validacoes(f)}
  {_secao_descobertas(f)}
  {_secao_manter(f)}
</main>
<script type="application/json" id="dados">{dados_js}</script>
<script>{JS}</script>
"""


def gerar(codigo_indice: str) -> str:
    return renderizar(coletar(carregar_catalogo().indices[codigo_indice]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera a página de transformações de um índice.")
    parser.add_argument("--indice", default="ipca15")
    parser.add_argument(
        "--verificar", action="store_true", help="só compara com o arquivo existente"
    )
    args = parser.parse_args(argv)

    html = gerar(args.indice)
    destino = caminho_pagina(args.indice)
    if args.verificar:
        atual = destino.read_text(encoding="utf-8") if destino.exists() else ""
        if atual != html:
            print(
                f"{destino.relative_to(RAIZ)} está desatualizada; rode sem --verificar",
                file=sys.stderr,
            )
            return 1
        print(f"{destino.relative_to(RAIZ)} em dia")
        return 0
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    print(f"{destino.relative_to(RAIZ)} gerada ({len(html) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
