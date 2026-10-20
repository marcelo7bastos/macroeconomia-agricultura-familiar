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
from macroaf.relatorios import graficos
from macroaf.relatorios.coleta import coletar
from macroaf.relatorios.graficos import MENOS, TRACO

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
        "Nove casos de harmonização não aceitos pelo mantenedor aguardam investigação; até lá, são "
        "quebra marcada. O do leite (pasteurizado → longa vida) é prioridade.",
        "issues #32 a #40 · METODOLOGIA.md 7.4",
    ),
    (
        "Se o projeto reporta ao IBGE os erros publicados que encontrou, em especial os da 3065.",
        "METODOLOGIA.md 6.4 · A-015",
    ),
    (
        "O IBGE ancorou o acumulado no ano de 12 categorias novas da 1387 num antecessor de outro "
        "código (ex.: Cursos diversos, Peito de frango → Frango em pedaços). Se essas ligações devem "
        "mudar o mapa de harmonização depende de revisão humana.",
        "METODOLOGIA.md 8.2 · A-023 · issue #48",
    ),
    (
        "Como o projeto absorve a próxima troca de POF (tabela nova no lugar da 7062).",
        "issue #27",
    ),
]


# Medidas que o projeto também calcula (onde falta o oficial ou por série longa), por coluna.
CALCULADA = {
    "variacao_acum_ano": '<span class="selo parcial">onde a 356 não mede a série (#42)</span>',
    "variacao_acum_12m": '<span class="selo parcial">onde falta ou não serve (#42)</span>',
    "numero_indice": '<span class="selo sim">por série longa, base 100 (#41)</span>',
    "variacao_acum_3m": '<span class="selo parcial">nos meses de erro publicado (#42)</span>',
    "variacao_acum_6m": '<span class="selo parcial">nos meses de erro publicado (#42)</span>',
}

# Indicadores da seção 5.2 do planejamento já calculados, com a issue que os entregou.
FEITOS = {
    "Índice base 100": '<span class="selo sim">feito (#41)</span>',
    "Acumulados em janelas": '<span class="selo sim">feito (#42)</span>',
    "Contribuição (p.p.)": '<span class="selo sim">feito (#43)</span>',
    "Contribuição dentro do grupo": '<span class="selo sim">feito (#43)</span>',
    "Difusão": '<span class="selo sim">feito (#44)</span>',
    "Sazonalidade": '<span class="selo sim">feito (#44)</span>',
}


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
        *(
            [
                {
                    "id": "serie",
                    "titulo": "Série longa",
                    "executiva": "Emenda as tabelas de POFs diferentes numa série só, mas apenas onde há prova de que a categoria é a mesma. Na dúvida, a série quebra.",
                    "entrada": "fato, dim_classificacao e o mapa de harmonização (reference/map_harmonizacao_"
                    + f["indice"]["codigo"]
                    + ".csv).",
                    "regra": "Mesmo código e mesmo id: continua. Id novo só com grafia diferente: continua. Qualquer outra mudança vira proposta e só continua depois de revisada por uma pessoa; até lá, é quebra marcada.",
                    "saida": "serie_longa: as linhas do fato com serie_id, início e fim da série e como ela entrou e saiu (início dos dados, novo, fundido, dividido, proposta não revisada...).",
                    "comando": "uv run python -m macroaf.transform.harmonizacao",
                    "codigo": "src/macroaf/transform/harmonizacao.py",
                    "numeros": [
                        ("Séries", _n(f["harmonizacao"]["series"]["total"])),
                        ("Linhas no mapa", _n(f["harmonizacao"]["linhas"])),
                        (
                            "Propostas a revisar",
                            _n(
                                sum(
                                    1
                                    for p in f["harmonizacao"]["propostas"]
                                    if p["situacao"] == "proposto"
                                )
                            ),
                        ),
                    ],
                }
            ]
            if f.get("harmonizacao")
            else []
        ),
        *(
            [
                {
                    "id": "indice",
                    "titulo": "Índice encadeado",
                    "executiva": "Transforma as variações mensais de cada série longa num índice que começa em 100. Dele saem os acumulados de qualquer janela por uma divisão.",
                    "entrada": "serie_longa e as exceções de cesta variável em reference/excecoes_validacao_"
                    + f["indice"]["codigo"]
                    + ".csv.",
                    "regra": "Índice do mês = índice do mês anterior vezes (1 + variação/100), com 100 no mês anterior ao início da série. Cada série começa de novo em 100: o índice nunca atravessa uma quebra. Mês faltando ou variação ausente param a transformação.",
                    "saida": "indice_"
                    + f["indice"]["codigo"]
                    + ": serie_id, mês, tabela, ids, nível, variação mensal, índice e a marca cesta_variavel.",
                    "comando": "uv run python -m macroaf.indicators.indice",
                    "codigo": "src/macroaf/indicators/indice.py",
                    "numeros": [
                        ("Séries", _n(f["indice_encadeado"]["series"])),
                        ("Linhas com cesta variável", _n(f["indice_encadeado"]["cesta_variavel"])),
                        (
                            "Maior desvio do geral para o número-índice da 3065",
                            f"{f['indice_encadeado']['desvio_max_1117']:.4f}%".replace(".", ","),
                        ),
                    ],
                }
            ]
            if f.get("indice_encadeado")
            else []
        ),
        *(
            [
                {
                    "id": "acumulados",
                    "titulo": "Acumulados por janela",
                    "executiva": "Variação acumulada em 3, 6, 12, 24 e 36 meses e no ano, para cada série. Onde o IBGE publica o mesmo número, vale o do IBGE.",
                    "entrada": "indice_"
                    + f["indice"]["codigo"]
                    + ", serie_longa (acumulados publicados por categoria), ref_geral e as exceções em reference/.",
                    "regra": "Calculado pelo índice: índice do mês dividido pelo de k meses antes. A janela que sai do início da série fica vazia. O oficial é preferido quando mede a mesma coisa: a janela cabe na série, e no acumulado no ano a série tem janeiro e o código não mudou (A-023). Em erro publicado pela fonte (A-015) que diverge do calculado, vale o calculado.",
                    "saida": "acumulados_"
                    + f["indice"]["codigo"]
                    + ": uma linha por série, mês e janela, com acumulado, origem (oficial ou calculado) e cesta_variavel (janela que contém mês com cesta variável).",
                    "comando": "uv run python -m macroaf.indicators.acumulados",
                    "codigo": "src/macroaf/indicators/acumulados.py",
                    "numeros": [
                        (f"Janela {j}", f"{_n(o)} oficiais, {_n(c)} calculados")
                        for j, o, c in f["acumulados"]["janelas"]
                    ],
                }
            ]
            if f.get("acumulados")
            else []
        ),
        *(
            [
                {
                    "id": "contribuicoes",
                    "titulo": "Contribuições",
                    "executiva": "Quanto cada grupo, item ou subitem pôs na variação do índice geral, em pontos percentuais, no mês e nos acumulados. Somadas, as dos grupos dão o geral.",
                    "entrada": "indice_" + f["indice"]["codigo"] + " e os pesos da serie_longa.",
                    "regra": "No mês: peso vezes variação, dividido pela soma dos pesos dos grupos daquele mês. No acumulado: cada mês da janela pesa pelo índice geral até o mês anterior. Participação no grupo: a contribuição dividida pela soma das do mesmo nível no grupo. Subitens in natura da 1646 ficam só pelo item (A-013).",
                    "saida": "contribuicoes_"
                    + f["indice"]["codigo"]
                    + ": uma linha por série, mês e janela (mes, 3m, 6m, 12m, 24m, 36m, ano), com contribuição e, no mês, participação no grupo.",
                    "comando": "uv run python -m macroaf.indicators.contribuicoes",
                    "codigo": "src/macroaf/indicators/contribuicoes.py",
                    "numeros": [
                        ("Linhas", _n(f["contribuicoes"]["linhas"])),
                        (
                            "Maior diferença mensal entre a soma dos grupos e o geral",
                            f"{f['contribuicoes']['diferenca_max_mes']:.4f} p.p.".replace(
                                ".", ",", 1
                            ),
                        ),
                    ],
                }
            ]
            if f.get("contribuicoes")
            else []
        ),
        *(
            [
                {
                    "id": "difusao",
                    "titulo": "Difusão e sazonalidade",
                    "executiva": "Difusão: quantos subitens subiram de preço no mês, em % (simples e pelo peso). Sazonalidade: como cada mês do ano costuma se comportar, pela média e mediana dos últimos anos.",
                    "entrada": "serie_longa (difusão) e indice_"
                    + f["indice"]["codigo"]
                    + " (sazonalidade).",
                    "regra": f"Difusão: subitens com variação maior que zero sobre os subitens coletados no mês (peso 0 fica fora, A-026); na ponderada, a soma dos pesos deles sobre a soma dos pesos. No geral e em cada grupo; a troca de cesta fica marcada. Sazonalidade: média e mediana da variação de cada mês do ano nos últimos {f['difusao']['anos']} anos, só com anos seguidos da própria série.",
                    "saida": "difusao_"
                    + f["indice"]["codigo"]
                    + " (mês e recorte) e sazonalidade_"
                    + f["indice"]["codigo"]
                    + " (série, mês do ano e ano final).",
                    "comando": "uv run python -m macroaf.indicators.difusao e macroaf.indicators.sazonalidade",
                    "codigo": "src/macroaf/indicators/difusao.py e sazonalidade.py",
                    "numeros": [
                        ("Meses com difusão", _n(f["difusao"]["meses"])),
                        (
                            f"Difusão simples em {_mes(f['difusao']['ultimo_mes'])}",
                            f"{f['difusao']['ultima_simples']:.1f}%".replace(".", ","),
                        ),
                        ("Linhas de sazonalidade", _n(f["difusao"]["linhas_sazonalidade"])),
                    ],
                }
            ]
            if f.get("difusao")
            else []
        ),
        {
            "id": "marts",
            "titulo": "Marts",
            "executiva": "As tabelas finais que o Power BI e o site leem, em CSV, com nomes de arquivo e de coluna estáveis.",
            "entrada": "Tudo montado de novo a partir do raw: classificação, fato, série longa e indicadores.",
            "regra": "Antes de gravar, roda as validações e confere os indicadores (índice geral contra a 3065, soma das contribuições dos grupos). Qualquer falha bloqueia: nada é gravado. A chave das linhas é o mês e a categoria publicada (tabela e id SIDRA); a série longa é atributo, porque muda com a revisão (decisão 0006). Só CSV, ordenado e arredondado, para o histórico do git crescer pouco a cada mês (decisão 0007).",
            "saida": "data/marts/"
            + f["indice"]["codigo"]
            + "_*.csv, o dicionário data/marts/README.md, data/metadata.json e o histórico de mudanças de série em reference/.",
            "comando": "uv run python -m macroaf.marts.publicar",
            "codigo": "src/macroaf/marts/publicar.py",
            "numeros": [(m["arquivo"], f"{_n(m['linhas'])} linhas") for m in f["marts"]]
            or [("Arquivos", "nenhum ainda")],
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
        no(
            "marts",
            850,
            221,
            140,
            "marts",
            f"{len(f['marts'])} arquivos" if f["marts"] else "a fazer",
            pendente=not f["marts"],
        ),
        no(
            "serie",
            670,
            21,
            140,
            "série longa",
            f"{_n(f['harmonizacao']['series']['total'])} séries",
        )
        if f.get("harmonizacao")
        else "",
        seta(590, 140, 666, 60, "mapa") if f.get("harmonizacao") else "",
        no(
            "indice",
            850,
            21,
            140,
            "índice base 100",
            f"{_n(f['indice_encadeado']['series'])} séries",
        )
        if f.get("indice_encadeado")
        else "",
        seta(810, 50, 846, 50) if f.get("indice_encadeado") else "",
        no(
            "acumulados",
            850,
            121,
            140,
            "acumulados",
            f"{len(f['acumulados']['janelas'])} janelas",
        )
        if f.get("acumulados")
        else "",
        seta(920, 79, 920, 117) if f.get("acumulados") else "",
        no(
            "contribuicoes",
            670,
            221,
            140,
            "contribuições",
            f"{_n(f['contribuicoes']['linhas'])} linhas",
        )
        if f.get("contribuicoes")
        else "",
        seta(900, 79, 800, 217) if f.get("contribuicoes") else "",
        seta(810, 250, 846, 250, "", pendente=not f["marts"]) if f.get("contribuicoes") else "",
        no(
            "difusao",
            670,
            311,
            140,
            "difusão",
            "e sazonalidade",
        )
        if f.get("difusao")
        else "",
        seta(810, 330, 880, 283, "", pendente=not f["marts"]) if f.get("difusao") else "",
        seta(920, 179, 920, 217, "", pendente=not f["marts"]) if f.get("acumulados") else "",
        seta(130, 150, 186, 150, "baixa"),
        seta(330, 140, 416, 55, "metadados"),
        seta(330, 150, 416, 150, "valores"),
        seta(330, 160, 416, 245, "3065"),
        seta(505, 79, 505, 117, "par tabela+id"),
        seta(590, 150, 666, 150),
        seta(590, 245, 666, 165, "gabarito"),
        seta(810, 165, 846, 240, "", pendente=not f["marts"]),
    ]
    altura = 380 if f.get("difusao") else 300
    return (
        f'<svg viewBox="0 0 1000 {altura}" role="img" aria-label="Fluxo dos dados: a API do IBGE alimenta '
        "a camada raw; os metadados viram a dim_classificacao, os valores viram o fato (ligado à dim "
        "pelo par tabela e id) e a tabela 3065 vira a referência; as validações conferem fato e "
        "referência; a série longa, pelo mapa de harmonização, vira o índice base 100, e dele saem "
        "os acumulados por janela e as contribuições em pontos percentuais; difusão e sazonalidade "
        'saem da série longa; os marts ainda não existem.">'
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
        linhas.append([nome, *celulas, CALCULADA.get(coluna, '<span class="selo nao">não</span>')])
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
                    CALCULADA.get(coluna, '<span class="selo nao">não</span>'),
                ]
            )
    if f.get("difusao"):
        linhas.append(
            [
                "Difusão (simples e ponderada) e sazonalidade por mês do ano",
                *['<span class="selo nao">não publicado</span>'] * len(dados),
                '<span class="selo sim">sim (#44)</span>',
            ]
        )
    if f.get("contribuicoes"):
        linhas.append(
            [
                "Contribuição em p.p. (no mês e nos acumulados) e participação no grupo",
                *['<span class="selo nao">não publicado</span>'] * len(dados),
                '<span class="selo sim">sim (#43)</span>',
            ]
        )
    if f.get("acumulados"):
        linhas.append(
            [
                "Acumulados em 3, 6, 24 e 36 meses por categoria",
                *['<span class="selo nao">não publicado</span>'] * len(dados),
                '<span class="selo sim">sim (#42)</span>',
            ]
        )
    if f.get("indice_encadeado"):
        linhas.append(
            [
                "Índice encadeado por série longa (base 100)",
                *['<span class="selo nao">não publicado</span>'] * len(dados),
                '<span class="selo sim">sim (#41)</span>',
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
    ]
    if f.get("resultados"):
        feito.append(
            "Calculamos, por série longa, o índice encadeado (base 100), os acumulados de 3 a 36 meses e no ano, as contribuições em pontos percentuais e a sazonalidade; e, pela cesta de cada mês, a difusão. "
            "Onde o IBGE publica o mesmo número, vale o oficial; o calculado entra onde falta ou onde o oficial não serve (erro publicado, ou acumulado que não mede a série), com a origem marcada."
        )
    else:
        feito.append(
            "Ainda não calculamos nenhuma inflação: todos os números do fato são oficiais. Os cálculos feitos até agora servem só para conferir."
        )
    if f["marts"]:
        feito.append(
            f"Publicamos {len(f['marts'])} arquivos CSV em data/marts/, que o Power BI lê pelo GitHub, com dicionário de dados e metadata.json. A publicação só acontece se todas as validações e conferências passam."
        )
    if f.get("harmonizacao"):
        h = f["harmonizacao"]
        conta = {
            s: sum(1 for p in h["propostas"] if p["situacao"] == s)
            for s in ["proposto", "revisado", "rejeitado"]
        }
        revisao = f"o mantenedor aceitou {_n(conta['revisado'])} propostas e não aceitou {_n(conta['rejeitado'])}"
        if conta["proposto"]:
            revisao += f"; {_n(conta['proposto'])} aguardam revisão"
        feito.insert(
            3,
            f"Ligamos as categorias entre POFs ({_n(h['linhas'])} ligações) e montamos {_n(h['series']['total'])} séries longas; "
            f"{revisao}. O que não foi aceito ou não foi revisado conta como quebra.",
        )
    quem = [
        ("macroaf.extract", "baixa e guarda o raw"),
        ("macroaf.transform", "monta dim, fato e referência"),
        ("macroaf.validate", "confere e bloqueia a publicação se algo não fecha"),
        ("macroaf.indicators", "calcula índice, acumulados, contribuições, difusão e sazonalidade"),
        ("macroaf.marts", "confere e publica os CSVs que o Power BI lê"),
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


def _pct(valor: float | None, casas: int = 2) -> str:
    return TRACO if valor is None else f"{valor:.{casas}f}".replace(".", ",").replace("-", MENOS)


def _secao_resultados(f: dict) -> str:
    r = f.get("resultados")
    if not r:
        return ""
    nome = f["indice"]["nome"]
    meses = [m for m, _ in r["doze_meses"]]
    trocas = [(m, "POF") for m in r["trocas"]]
    doze = graficos.linha(
        f"{nome} acumulado em 12 meses, índice geral, de {_mes(meses[0])} a {_mes(meses[-1])}",
        meses,
        [("12 meses", "serie-1", [v for _, v in r["doze_meses"]])],
        marcas=trocas,
    )
    grupos = r["grupos"]
    contrib_12m = graficos.barras(
        f"Contribuição de cada grupo para o {nome} em 12 meses até {_mes(r['ultimo_mes'])}, em pontos percentuais",
        [g["nome"] for g in grupos],
        [g["contribuicao_12m"] for g in grupos],
        unidade=" p.p.",
    )
    contrib_mes = graficos.barras(
        f"Contribuição de cada grupo para o {nome} em {_mes(r['ultimo_mes'])}, em pontos percentuais",
        [g["nome"] for g in grupos],
        [g["contribuicao_mes"] for g in grupos],
        unidade=" p.p.",
        casas=3,
    )
    dif = r["difusao"]
    difusao = graficos.linha(
        f"Difusão do {nome}: porcentagem dos subitens com alta de preço, simples e ponderada pelo peso",
        [m for m, _, _ in dif],
        [
            ("simples", "serie-1", [v for _, v, _ in dif]),
            ("ponderada", "serie-2", [v for _, _, v in dif]),
        ],
        marcas=trocas,
    )
    saz = r["sazonalidade"]
    sazonalidade = graficos.barras(
        f"Variação média de cada mês do ano no índice geral, {saz['ano_final'] - saz['anos'] + 1} a {saz['ano_final']}",
        [graficos.MESES[int(m) - 1] for m, _, _ in saz["meses"]],
        [media for _, media, _ in saz["meses"]],
        unidade="%",
        altura_barra=22,
        largura_rotulo=60,
    )
    c = r["conferencias"]
    conferencias = [
        [
            "Índice encadeado do geral",
            "número-índice (1117) da 3065",
            f"desvio máximo de {_pct(c['desvio_1117'], 4)}%",
        ],
        [
            "Acumulados do geral em 3, 6 e 12 meses e no ano",
            "1118, 1119, 1120 e 356 da 3065",
            f"diferença máxima de {_pct(c['geral_diferenca'], 3)} p.p. em {_n(c['geral_valores'])} valores (fora os {_n(c['erros_3065'])} erros publicados)",
        ],
        [
            "Acumulado em 12 meses por categoria",
            "1120 das tabelas de dados",
            f"diferença máxima de {_pct(c['doze_diferenca'], 3)} p.p. em {_n(c['doze_valores'])} valores",
        ],
        [
            "Soma das contribuições dos grupos no mês",
            "variação do geral",
            f"diferença máxima de {_pct(c['grupos_mes'], 4)} p.p. em {_n(c['grupos_meses'])} meses",
        ],
        [
            "Soma das contribuições dos grupos nos acumulados",
            "acumulado calculado do geral",
            f"diferença máxima de {_pct(c['grupos_acumulados'], 3)} p.p.",
        ],
    ]
    tabela_grupos = _tabela_html(
        ["Grupo", "Peso", "Variação no mês", "Contribuição no mês", "Contribuição em 12 meses"],
        [
            [
                escape(g["nome"]),
                _pct(g["peso"]),
                f"{_pct(g['variacao'])}%",
                f"{_pct(g['contribuicao_mes'], 3)} p.p.",
                f"{_pct(g['contribuicao_12m'], 3)} p.p.",
            ]
            for g in grupos
        ],
    )
    ancora = ""
    if r.get("ancora"):
        a = r["ancora"]
        ancora = f"""
  <h3>Por que nem todo número oficial serve: o acumulado no ano na troca de POF</h3>
  <p>Na troca de POF, o IBGE publica o acumulado no ano (variável 356) seguindo o <b>código</b> da categoria, não a série longa (A-023). Em geral, quando o código é novo, o acumulado recomeça no mês da troca; há exceções na troca de 2006, em que o IBGE encadeou desde janeiro por um antecessor de outro código (METODOLOGIA 8.2). Exemplo: <b>{escape(a["nome_antes"] or "")}</b> virou <b>{escape(a["nome_depois"])}</b>; a revisão emendou as duas numa série só ({escape(a["serie_id"])}). O IBGE trata a categoria como nova e acumula só desde a troca; a série longa acumula desde janeiro. Por isso, aqui, o projeto usa o calculado.</p>
  {_tabela_html(["Mês", "Variação no mês", "356 publicada (desde a troca)", "Acumulado da série (desde janeiro)"], [[_mes(m), f"{_pct(v)}%", f"{_pct(pub)}%", f"<b>{_pct(acu)}%</b>"] for m, v, pub, acu in a["linhas"]])}"""
    return f"""
<section id="resultados" class="secao">
  <h2>Resultados</h2>
  <p>Os números que saem do pipeline, para o índice geral e os grupos. Cada gráfico tem a tabela dos dados ao lado ou abaixo; passe o mouse sobre as linhas para ver os valores.</p>
  <div class="destaques">
    <div class="destaque"><span>{escape(nome)} em {_mes(r["ultimo_mes"])}</span><b>{_pct(r["geral_mes"])}%</b></div>
    <div class="destaque"><span>Em 12 meses</span><b>{_pct(r["geral_12m"])}%</b></div>
    <div class="destaque"><span>Subitens com alta no mês</span><b>{_pct(dif[-1][1], 1)}%</b></div>
  </div>
  <h3>Acumulado em 12 meses</h3>
  <figure><div class="rolagem">{doze}</div><div class="dica" hidden></div>
    <figcaption>Índice geral, acumulado em 12 meses. As linhas verticais marcam as trocas de POF; no geral não há quebra, porque a 3065 publica a série inteira.</figcaption></figure>
  <h3>Quem puxou a inflação</h3>
  <div class="abas" role="group" aria-label="Período das contribuições">
    <button type="button" class="aba ativa" data-contrib="12m" id="contrib-12m">12 meses</button>
    <button type="button" class="aba" data-contrib="mes" id="contrib-mes">{_mes(r["ultimo_mes"])}</button>
  </div>
  <figure data-painel-contrib="12m"><div class="rolagem">{contrib_12m}</div>
    <figcaption>Contribuição de cada grupo, em pontos percentuais: somadas, dão o acumulado do índice geral em 12 meses ({_pct(r["geral_12m"])}%).</figcaption></figure>
  <figure data-painel-contrib="mes" hidden><div class="rolagem">{contrib_mes}</div>
    <figcaption>Contribuição de cada grupo no mês: peso vezes variação, dividido pela soma dos pesos dos grupos (100, salvo erro da fonte). Somadas, dão a variação do geral ({_pct(r["geral_mes"])}%).</figcaption></figure>
  <details><summary>Tabela dos grupos</summary>{tabela_grupos}</details>
  <h3>Difusão</h3>
  <figure><div class="rolagem">{difusao}</div><div class="dica" hidden></div>
    <figcaption><span class="chave serie-1"></span> simples (porcentagem dos subitens com alta) e <span class="chave serie-2"></span> ponderada (pelo peso dos subitens). A cesta muda a cada troca de POF (linhas verticais), então a difusão compara a parte da cesta que subiu, não a mesma lista de produtos.</figcaption></figure>
  <h3>Sazonalidade</h3>
  <figure><div class="rolagem">{sazonalidade}</div>
    <figcaption>Média da variação de cada mês do ano no índice geral, nos últimos {saz["anos"]} anos ({saz["ano_final"] - saz["anos"] + 1} a {saz["ano_final"]}).</figcaption></figure>
  <h3>Os indicadores conferem com o IBGE</h3>
  <p>Onde o IBGE publica o mesmo número, o calculado pelo projeto tem de dar igual, dentro do erro de arredondamento. Testes automáticos travam estas conferências.</p>
  {_tabela_html(["O que", "Comparado com", "Resultado"], conferencias)}
  {ancora}
</section>"""


GLOSSARIO = [
    (
        "POF",
        "Pesquisa de Orçamentos Familiares. Define a cesta e os pesos do índice; a cada POF nova, o IBGE abre uma tabela nova.",
    ),
    (
        "Grupo, subgrupo, item, subitem",
        "Os níveis da classificação, do mais agregado ao mais detalhado. O nível sai do número de dígitos do código IBGE (1, 2, 4 e 7).",
    ),
    (
        "Código IBGE e id SIDRA",
        "O código diz a posição na árvore; o id diz qual definição vale naquela tabela. O mesmo código pode ter ids diferentes.",
    ),
    (
        "355, 356, 1120, 357",
        "Variáveis do SIDRA: variação mensal, acumulada no ano, acumulada em 12 meses e peso.",
    ),
    ("3065", "Tabela com só o índice geral, do início ao fim, usada como gabarito."),
    (
        "Série longa",
        "Uma categoria acompanhada através das tabelas de POFs diferentes, emendada só onde há prova de que é a mesma.",
    ),
    (
        "Quebra",
        "Ponto em que a série longa termina e outra começa, porque não há prova de que a categoria continua.",
    ),
    (
        "Índice encadeado",
        "Número que começa em 100 e acumula as variações mensais da série; dele saem os acumulados.",
    ),
    ("p.p.", "Pontos percentuais: diferença entre duas porcentagens, ou parte de uma porcentagem."),
    (
        "Contribuição",
        "A parte da variação do índice geral, em p.p., que vem de cada grupo, item ou subitem.",
    ),
    ("Difusão", "Porcentagem dos subitens cujo preço subiu no mês."),
    (
        "Cesta variável",
        "Na POF 1995-96, os pesos dos produtos in natura mudavam mês a mês com a safra (A-013).",
    ),
]


def _secao_glossario() -> str:
    itens = "".join(f"<dt>{escape(t)}</dt><dd>{escape(d)}</dd>" for t, d in GLOSSARIO)
    return f"""
<section id="glossario" class="secao">
  <h2>Glossário</h2>
  <dl class="glossario">{itens}</dl>
</section>"""


def _texto_series_rastreio(f: dict) -> str:
    """Quantas séries longas o código rastreado atravessa, a partir dos dados."""
    series = {}
    for r in f["rastreios"]:
        if r.get("indicadores"):
            i = r["indicadores"]
            series[i["serie_id"]] = (i["serie_inicio"], i["serie_fim"], r["dim"]["nome"])
    if len(series) <= 1:
        return "O código está numa série longa só, sem quebra."
    partes = "; ".join(
        f"<code>{escape(s)}</code> ({escape(n)}, {_mes(a)} a {_mes(b)})"
        for s, (a, b, n) in sorted(series.items(), key=lambda x: x[1][0])
    )
    return (
        f"O código atravessa {len(series)} séries longas: {partes}. Onde a série muda, o IBGE "
        "reformulou a categoria (id SIDRA novo) e a emenda não foi aceita na revisão; o índice "
        "recomeça em 100 (veja a decisão na seção Harmonização)."
    )


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
  <p>O mesmo código (<code>1111004</code>) no último mês de cada tabela: o registro como veio da API, a linha da classificação, a linha no fato e, por fim, os indicadores da série longa. {_texto_series_rastreio(f)}</p>
  <div class="abas" role="group" aria-label="Escolha a tabela">{botoes}</div>
  <div id="rastreio" class="rastreio" aria-live="polite"></div>
</section>"""


def _secao_harmonizacao(f: dict) -> str:
    h = f.get("harmonizacao")
    if not h:
        return ""
    transicoes = sorted({c["transicao"] for c in h["contagem"]})
    tipos = ["identico", "renomeado", "fundido", "dividido", "descontinuado", "novo"]
    linhas_contagem = []
    for tr in transicoes:
        celulas = []
        for tipo in tipos:

            def conta(situacao, tr=tr, tipo=tipo):
                return sum(
                    c["n"]
                    for c in h["contagem"]
                    if c["transicao"] == tr
                    and c["tipo_correspondencia"] == tipo
                    and c["situacao"] == situacao
                )

            partes = [_n(conta("automatico"))] if conta("automatico") else []
            for situacao, classe, rotulo in [
                ("revisado", "sim", "aceitas"),
                ("rejeitado", "falha", "não aceitas"),
                ("proposto", "parcial", "a revisar"),
            ]:
                if conta(situacao):
                    partes.append(
                        f'<span class="selo {classe}">{_n(conta(situacao))} {rotulo}</span>'
                    )
            celulas.append(" ".join(partes) or "·")
        linhas_contagem.append([f"POF {tr}", *celulas])
    s = h["series"]
    niveis = ["geral", "grupo", "subgrupo", "item", "subitem"]
    linhas_series = [[n, _n(s["por_nivel"][n]), _n(s["completas_por_nivel"][n])] for n in niveis]

    def linha(p: dict) -> list[str]:
        peso = lambda v: "·" if v is None else str(v).replace(".", ",")  # noqa: E731
        situacao = {
            "revisado": f'<span class="selo sim">aceita ({escape(p["revisor"] or "")})</span>',
            "rejeitado": f'<span class="selo falha">não aceita ({escape(p["revisor"] or "")})</span>',
            "proposto": '<span class="selo parcial">a revisar</span>',
        }.get(p["situacao"], '<span class="selo nao">automático</span>')
        if p.get("observacao"):
            situacao += f"<br><small>{escape(p['observacao'])}</small>"
        return [
            f"<code>{escape(p['id'])}</code>",
            escape(p["transicao"]),
            escape(p["origem"] or "·"),
            escape(p["destino"] or "·"),
            f"<b>{escape(p['tipo'])}</b>",
            situacao,
            f"{peso(p['peso_origem_fim'])} → {peso(p['peso_destino_inicio'])}",
            escape(p["criterio"]),
        ]

    filtros = "".join(
        f'<button type="button" class="aba" data-transicao="{escape(tr)}" id="transicao-{i}">{escape(tr)}</button>'
        for i, tr in enumerate(transicoes)
    )
    cab = [
        "Id",
        "POF",
        "Origem",
        "Destino",
        "Tipo sugerido",
        "Situação",
        "Peso fim → início",
        "Critério",
    ]
    return f"""
<section id="harmonizacao" class="secao">
  <h2>Harmonização entre POFs</h2>
  <p>A cada troca de POF o IBGE muda parte das categorias. Para montar a série longa, cada categoria de uma tabela é ligada à da tabela seguinte com um tipo: <b>idêntico</b> ou <b>renomeado</b> (a série continua), <b>fundido</b> ou <b>dividido</b> (a série continua só no nível de cima e quebra no detalhe) e <b>descontinuado</b> ou <b>novo</b> (a série termina ou começa).</p>
  <p><b>Na dúvida, quebra.</b> Uma ligação só emenda a série se houver prova: o mesmo id SIDRA, ou só a grafia mudou. Todo o resto é proposta e só emenda depois de revisada por uma pessoa. Encerrar uma série nunca esconde nada; emendar errado esconde.</p>
  {_tabela_html(["Troca", *tipos], linhas_contagem)}
  <h3>Séries longas hoje</h3>
  <p>{_n(s["linhas"])} linhas em {_n(s["total"])} séries. "Completas" vão do primeiro ao último mês dos dados sem quebra.</p>
  {_tabela_html(["Nível", "Séries", "Completas"], linhas_series)}
  <details>
  <summary>Propostas e decisões da revisão ({_n(len(h["propostas"]))} ligações)</summary>
  <p>Cada linha é uma ligação sugerida pelas regras, com a evidência (nomes, ids, critério, peso no último mês da tabela antiga e no primeiro da nova) e a decisão do revisor. Aceita emenda a série (renomeado) ou confirma a fusão ou divisão; não aceita mantém a quebra e cita a issue de investigação. A revisão é feita na página <code>docs/revisao/harmonizacao_{escape(f["indice"]["codigo"])}.html</code>.</p>
  <div class="controles">
    <label for="busca-propostas">Buscar:</label>
    <input type="search" id="busca-propostas" placeholder="nome ou código">
    <div class="abas" role="group" aria-label="Filtrar por troca de POF">
      <button type="button" class="aba ativa" data-transicao="todas" id="transicao-todas">Todas</button>{filtros}
    </div>
  </div>
  {_tabela_html(cab, [linha(p) for p in h["propostas"]], "propostas")}
  </details>
  <details>
    <summary>O que some e o que aparece sem candidato ({_n(len(h["entram_saem"]))} categorias)</summary>
    <p>Use esta lista para achar fusões que as regras não viram (por exemplo, "Massa para pizza" e "Massa semipreparada").</p>
    {_tabela_html(cab, [linha(p) for p in h["entram_saem"]], "propostas")}
  </details>
</section>"""


def _secao_existe(f: dict) -> str:
    planejados = [
        [
            escape(i["indicador"]),
            escape(i["definicao"]),
            escape(i["teste"]),
            FEITOS.get(i["indicador"], '<span class="selo nao">a fazer (#7)</span>'),
        ]
        for i in f["indicadores_planejados"]
    ]
    return f"""
<section id="existe" class="secao">
  <h2>O que já existe e o que não existe</h2>
  <p>As medidas abaixo estão no fato <b>como o IBGE publica</b>, para todos os níveis (geral, grupo, subgrupo, item e subitem). A porcentagem é a parte das linhas da tabela que tem valor.</p>
  {_existe(f)}
  <ul class="notas">
    <li>O acumulado em 12 meses não existe nas tabelas 1646 e 1387 e vem vazio em parte da 1705 e da 7062 (A-009). Onde falta, acumulados_{f["indice"]["codigo"]} traz o calculado pelo índice, com origem marcada (#42).</li>
    <li>Agregação: o projeto não recalcula a variação de grupos e itens a partir dos subitens; usa a publicada. Médias ponderadas servem só para conferir com o IBGE.</li>
    <li>Índice encadeado: calculado por série longa, a partir da variação mensal oficial. O do geral reproduz o número-índice da 3065. Os acumulados por janela (#42) e as contribuições (#43) partem dele.</li>
    <li>Acumulado no ano no ano da troca de POF: o IBGE ancora janeiro pelo código, não pela série longa; para código novo, começa no mês da troca (A-023). A 356 só vale como acumulado da série quando a série tem janeiro e o código não mudou; o índice encadeado só dá o acumulado no ano nesse caso.</li>
    <li>Série longa: emenda as tabelas só onde há prova de que a categoria é a mesma; o resto fica como quebra marcada até a revisão humana (seção Harmonização).</li>
  </ul>
  <h3>Indicadores planejados</h3>
  {_tabela_html(["Indicador", "Definição", "Teste previsto", "Situação"], planejados)}
  <p>Marts publicados para o Power BI e o site: <b>{_n(len(f["marts"]))}</b> arquivos em <code>data/marts/</code>, com o dicionário em <code>data/marts/README.md</code> (#8).</p>
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
  <p>Esta página é gerada pelo código a partir dos dados do repositório. Ninguém a edita à mão. Todo mês, o GitHub Actions roda <code>uv run python -m macroaf.pipeline --indice {codigo}</code>, que faz tudo abaixo e só publica se nada falhar (#9). Etapa por etapa:</p>
  <pre><code>uv run python -m macroaf.extract.atualizar
uv run python -m macroaf.transform.{codigo}
uv run python -m macroaf.validate.{codigo}
uv run python -m macroaf.transform.harmonizacao --indice {codigo}
uv run python -m macroaf.indicators.indice --indice {codigo}
uv run python -m macroaf.indicators.acumulados --indice {codigo}
uv run python -m macroaf.indicators.contribuicoes --indice {codigo}
uv run python -m macroaf.indicators.difusao --indice {codigo}
uv run python -m macroaf.indicators.sazonalidade --indice {codigo}
uv run python -m macroaf.marts.publicar --indice {codigo}
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
  --serie-1: #2a78d6; --serie-2: #eb6834; --positivo: #2a78d6; --negativo: #e34948; --eixo: #c3c2b7;
  --fonte-titulo: "IBM Plex Sans Condensed", "Arial Narrow", system-ui, sans-serif;
  --fonte-texto: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --fonte-dados: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --papel: #11161d; --superficie: #19202a; --tinta: #e6eaf0; --suave: #9aa6b5; --linha: #2c3643;
  --destaque: #7db4e6; --destaque-fundo: #1b2e42; --pof0: #3d5f80; --pof1: #3b6b63; --pof2: #6e5f33; --pof3: #5d4a6b;
  --sim: #7dd3a0; --sim-fundo: #183528; --parcial: #e6c070; --parcial-fundo: #3a3018; --nao: #8b95a3; --nao-fundo: #222a35;
  --falha: #f2a49d; --falha-fundo: #3d1d1b; --alerta-fundo: #2e2717; --serie-1: #3987e5; --serie-2: #d95926; --positivo: #3987e5; --negativo: #e66767; --eixo: #4a5563; color-scheme: dark; } }
:root[data-theme="dark"] {
  --papel: #11161d; --superficie: #19202a; --tinta: #e6eaf0; --suave: #9aa6b5; --linha: #2c3643;
  --destaque: #7db4e6; --destaque-fundo: #1b2e42; --pof0: #3d5f80; --pof1: #3b6b63; --pof2: #6e5f33; --pof3: #5d4a6b;
  --sim: #7dd3a0; --sim-fundo: #183528; --parcial: #e6c070; --parcial-fundo: #3a3018; --nao: #8b95a3; --nao-fundo: #222a35;
  --falha: #f2a49d; --falha-fundo: #3d1d1b; --alerta-fundo: #2e2717; --serie-1: #3987e5; --serie-2: #d95926; --positivo: #3987e5; --negativo: #e66767; --eixo: #4a5563; color-scheme: dark; }
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
input[type="search"] { font: inherit; padding: 6px 10px; border: 1px solid var(--linha); border-radius: 6px; background: var(--superficie); color: var(--tinta); min-width: 0; width: 16rem; max-width: 100%; }
details { background: var(--superficie); border: 1px solid var(--linha); border-radius: 6px; padding: 12px 16px; display: grid; gap: 10px; }
summary { cursor: pointer; font-weight: 600; }
table.propostas td:nth-child(8) { min-width: 220px; color: var(--suave); }
.notas { margin: 0; padding-left: 18px; display: grid; gap: 6px; color: var(--suave); max-width: 80ch; }
ol.descobertas { margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; }
ol.descobertas .cod { display: inline-block; min-width: 4.2em; color: var(--destaque); font-weight: 600; }
pre { background: var(--superficie); border: 1px solid var(--linha); border-radius: 6px; padding: 12px; overflow-x: auto; margin: 0; }
[hidden] { display: none !important; }
body.executiva .tecnico { display: none; }
svg.grafico { min-width: 560px; } svg.grafico .grade { stroke: var(--linha); } svg.grafico .eixo { stroke: var(--eixo); stroke-width: 1.2; }
svg .linha { fill: none; stroke-width: 2; stroke-linejoin: round; } svg .linha.serie-1 { stroke: var(--serie-1); } svg .linha.serie-2 { stroke: var(--serie-2); }
svg .barra-h.positivo { fill: var(--positivo); } svg .barra-h.negativo { fill: var(--negativo); }
svg .barra-g:hover .barra-h { opacity: 0.8; } svg .valor { fill: var(--tinta); font-variant-numeric: tabular-nums; }
svg .regua { stroke: var(--suave); stroke-width: 1; stroke-dasharray: 3 3; }
figure { position: relative; }
.dica { position: absolute; top: 4px; right: 8px; background: var(--superficie); border: 1px solid var(--linha); border-radius: 6px; padding: 6px 10px; font-size: 0.85rem; font-variant-numeric: tabular-nums; pointer-events: none; max-width: 90%; }
.chave { display: inline-block; width: 14px; height: 3px; border-radius: 2px; vertical-align: middle; }
.chave.serie-1 { background: var(--serie-1); } .chave.serie-2 { background: var(--serie-2); }
.destaques { display: flex; flex-wrap: wrap; gap: 12px; }
.destaque { background: var(--superficie); border: 1px solid var(--linha); border-radius: 6px; padding: 12px 16px; display: grid; gap: 2px; min-width: 160px; }
.destaque span { color: var(--suave); font-size: 0.85rem; } .destaque b { font-family: var(--fonte-titulo); font-size: 1.8rem; font-variant-numeric: tabular-nums; }
dl.glossario { margin: 0; display: grid; grid-template-columns: minmax(120px, max-content) 1fr; gap: 8px 16px; max-width: 90ch; }
dl.glossario dt { font-weight: 600; } dl.glossario dd { margin: 0; color: var(--suave); }
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
    <div class="bloco"><h3>3. fato</h3><small>uma linha, variáveis em colunas; null = não publicado</small><pre>${json(r.fato)}</pre></div>
    ${r.indicadores ? `<div class="bloco"><h3>4. Indicadores</h3><small>série ${esc(r.indicadores.serie_id)}, de ${esc(r.indicadores.serie_inicio)} a ${esc(r.indicadores.serie_fim)}</small><pre>${json(r.indicadores)}</pre></div>` : ''}`;
}
document.querySelectorAll('[data-rastreio]').forEach((b) => b.addEventListener('click', () => mostrarRastreio(Number(b.dataset.rastreio))));
mostrarRastreio(dados.rastreios.length - 1);

document.querySelectorAll('[data-filtro]').forEach((b) => b.addEventListener('click', () => {
  document.querySelectorAll('[data-filtro]').forEach((o) => o.classList.toggle('ativa', o === b));
  document.querySelectorAll('table.excecoes tbody tr').forEach((tr) => {
    tr.hidden = b.dataset.filtro !== 'todas' && !tr.querySelector('.selo.' + b.dataset.filtro);
  });
}));

let transicaoAtiva = 'todas';
const busca = document.getElementById('busca-propostas');
function filtrarPropostas() {
  const termo = (busca ? busca.value : '').toLowerCase();
  document.querySelectorAll('table.propostas tbody tr').forEach((tr) => {
    const texto = tr.textContent.toLowerCase();
    const naTransicao = transicaoAtiva === 'todas' || tr.children[1].textContent === transicaoAtiva;
    tr.hidden = !(naTransicao && (!termo || texto.includes(termo)));
  });
}
document.querySelectorAll('[data-transicao]').forEach((b) => b.addEventListener('click', () => {
  transicaoAtiva = b.dataset.transicao;
  document.querySelectorAll('[data-transicao]').forEach((o) => o.classList.toggle('ativa', o === b));
  filtrarPropostas();
}));
if (busca) busca.addEventListener('input', filtrarPropostas);

document.querySelectorAll('svg.grafico-linha').forEach((svg) => {
  const rotulos = JSON.parse(svg.dataset.rotulos);
  const x0 = Number(svg.dataset.x0), dx = Number(svg.dataset.dx);
  const regua = svg.querySelector('.regua');
  const dica = svg.closest('figure').querySelector('.dica');
  svg.addEventListener('mousemove', (ev) => {
    const caixa = svg.getBoundingClientRect();
    const x = (ev.clientX - caixa.left) * (svg.viewBox.baseVal.width / caixa.width);
    const i = Math.max(0, Math.min(rotulos.length - 1, Math.round((x - x0) / dx)));
    const xi = x0 + i * dx;
    regua.setAttribute('x1', xi); regua.setAttribute('x2', xi); regua.setAttribute('visibility', 'visible');
    dica.textContent = rotulos[i]; dica.hidden = false;
  });
  svg.addEventListener('mouseleave', () => { regua.setAttribute('visibility', 'hidden'); dica.hidden = true; });
});

document.querySelectorAll('[data-contrib]').forEach((b) => b.addEventListener('click', () => {
  document.querySelectorAll('[data-contrib]').forEach((o) => o.classList.toggle('ativa', o === b));
  document.querySelectorAll('[data-painel-contrib]').forEach((f) => { f.hidden = f.dataset.painelContrib !== b.dataset.contrib; });
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


def _renderizar_indice(f: dict) -> str:
    """Relatório por configuração, sem exemplos ou referências exclusivos do piloto."""
    nome = escape(f["indice"]["nome"])
    codigo = escape(f["indice"]["codigo"])
    referencia = next(t for t in f["tabelas"] if t["papel"] == "referencia")
    tabelas = _tabela_html(
        ["Tabela", "Papel", "POF", "Início", "Fim", "Meses no raw"],
        [
            [
                str(t["tabela"]),
                t["papel"],
                t["versao_pof"] or "—",
                t["inicio"],
                t["fim"],
                str(t["meses_raw"]),
            ]
            for t in f["tabelas"]
        ],
    )
    validacoes = _tabela_html(
        ["Verificação", "Situação", "Verificados", "Falhas", "Exceções"],
        [
            [
                v["validacao"],
                "ok" if v["ok"] else "FALHA",
                str(v["verificados"]),
                str(v["falhas"]),
                str(v["excecoes_aplicadas"]),
            ]
            for v in f["validacoes"]
        ],
    )
    resultados = f["resultados"]
    grupos = _tabela_html(
        ["Grupo", "Peso (%)", "Variação mensal (%)", "Contribuição mensal (p.p.)"],
        [
            [g["nome"], _pct(g["peso"]), _pct(g["variacao"]), _pct(g["contribuicao_mes"], 3)]
            for g in resultados["grupos"]
        ],
    )
    harmonizacao = f["harmonizacao"]
    propostas = sum(c["n"] for c in harmonizacao["contagem"] if c["situacao"] == "proposto")
    fontes = _tabela_html(
        ["Janela", "Oficiais", "Calculados"],
        [[j, str(o), str(c)] for j, o, c in f["acumulados"]["janelas"]],
    )
    return f"""<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>Transformações do {nome}</title><meta name="viewport" content="width=device-width">
<style>{CSS}</style><main class="pagina">
<header class="topo"><p class="olho">Brasil · dados oficiais do IBGE</p>
<h1>Transformações do {nome}</h1><p>{escape(f["indice"]["descricao"])}.
Detalhe de {f["periodo"]["inicio"]} a {f["periodo"]["fim"]}.</p></header>
<section class="secao"><h2>Da fonte à publicação</h2>
<p>APIs oficiais → raw auditável → classificação e fato → validações → harmonização → indicadores
→ CSV e metadados. O raw preserva a resposta original, a URL, o SHA-256 e a data de coleta.</p>
<p>{f["fato"]["linhas"]:,} observações; {f["dim"]["linhas"]} categorias por versão;
{f["raw"]["arquivos"]} arquivos raw deste índice.</p>{tabelas}</section>
<section class="secao"><h2>Como os dados são tratados</h2>
<p>A hierarquia vem do código IBGE: grupo, subgrupo, item e subitem. A chave combina tabela e
id SIDRA. Ausentes permanecem ausentes, nunca zero. A tabela {referencia["tabela"]} é a referência
oficial do geral; o raw mantém sua cobertura original e o staging recorta o intervalo do detalhe.</p>
<p>Valores oficiais têm preferência. Calculados são identificados pela origem. As mudanças entre
POFs usam um mapa próprio; propostas não revisadas preservam a quebra. Há {propostas} ligações
propostas pendentes; elas não são apresentadas como continuidades aprovadas.</p>
<a href="../revisao/harmonizacao_{codigo}.html">Examinar a harmonização</a></section>
<section class="secao"><h2>Validações</h2>{validacoes}
<p>Sentinelas divergentes: {f["sentinelas"]}. Falhas sem explicação bloqueiam a publicação.
A tolerância de comparação entre ambientes não substitui as validações contra o IBGE.</p></section>
<section class="secao"><h2>Resultados em {resultados["ultimo_mes"]}</h2>
<p>Índice geral no mês: {_pct(resultados["geral_mes"])}%; em 12 meses:
{_pct(resultados["geral_12m"])}%. Referência oficial: tabela {referencia["tabela"]}.</p>{grupos}
<h3>Acumulados: oficial ou calculado</h3>{fontes}</section>
<section class="secao"><h2>Saídas e reprodução</h2>
<p><a href="../../data/marts/{codigo}_README.md">Dicionário dos CSVs</a> ·
<a href="../../data/metadata.json">Metadados e hashes</a> ·
<a href="../indices/{codigo}.md">Ficha da fonte</a> ·
<a href="../METODOLOGIA.md">Metodologia</a></p>
<pre>uv run python -m macroaf.pipeline --indice {codigo}
uv run python -m macroaf.validate.ipca15 --indice {codigo}</pre>
<p>O índice não inclui projeções. O período anterior ao detalhe disponível não é preenchido
com categorias artificiais nem com observações de outro índice.</p></section></main></html>"""


def renderizar(f: dict) -> str:
    if f["indice"]["codigo"] != "ipca15":
        return _renderizar_indice(f)
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
      <a href="#resumo">Em resumo</a><a href="#resultados">Resultados</a><a href="#fluxo">Caminho dos dados</a><a href="#tempo">Linha do tempo</a>
      <a href="#juncao">Como as tabelas se juntam</a><a href="#harmonizacao">Harmonização</a><a href="#existe">O que existe</a>
      <a href="#validacoes">Validações</a><a href="#descobertas">Descobertas</a><a href="#glossario">Glossário</a><a href="#manter">Manter atualizado</a>
    </nav>
  </header>
  {_secao_resumo(f)}
  {_secao_resultados(f)}
  <section id="fluxo" class="secao">
    <h2>O caminho dos dados</h2>
    <p>Clique numa etapa para ver o que entra, a regra aplicada, o que sai e o comando que a executa. A visão executiva esconde os detalhes técnicos.</p>
    <figure>
      <div class="rolagem">{_svg_fluxo(f)}</div>
      <figcaption>Os metadados viram a classificação, os valores viram o fato e a tabela 3065 vira o gabarito do índice geral. {"" if f["marts"] else "A caixa tracejada ainda não existe."}</figcaption>
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
  {_secao_harmonizacao(f)}
  {_secao_existe(f)}
  {_secao_validacoes(f)}
  {_secao_descobertas(f)}
  {_secao_glossario()}
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
