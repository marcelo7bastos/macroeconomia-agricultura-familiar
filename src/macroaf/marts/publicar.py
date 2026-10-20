"""Publica os marts de um índice em `data/marts/` (#8, decisões 0006 e 0007).

Monta tudo a partir do raw (classificação, fato, série longa e indicadores), confere e só então
grava. Uma validação que falha, uma sentinela alterada ou um indicador fora da conferência
bloqueiam a publicação: nada é escrito.

Saídas (nomes estáveis; o Power BI lê pelas URLs do raw do GitHub):

- `data/marts/<indice>_categorias.csv`, `_mensal.csv`, `_acumulados.csv`, `_contribuicoes.csv`,
  `_difusao.csv`: CSV UTF-8, separador vírgula, ponto decimal, linhas em ordem fixa;
- `data/marts/README.md`: dicionário de dados, gerado do dicionário abaixo;
- `data/metadata.json`: último mês, coleta, validações e conferências;
- `reference/historico_series_<indice>.csv`: mudanças de `serie_id` entre publicações (0006).

Uso:

    uv run python -m macroaf.marts.publicar --indice ipca15
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from macroaf.catalogo import RAIZ, Indice, carregar_catalogo
from macroaf.extract.raw import METADADOS, ArmazemRaw
from macroaf.indicators.calcular import calcular_indicadores
from macroaf.indicators.contribuicoes import limite_reconciliacao
from macroaf.transform.classificacao import montar_dim_classificacao
from macroaf.transform.harmonizacao import id_ligacao, ler_mapa, montar_serie_longa
from macroaf.transform.ipca15 import montar_fato, montar_referencia
from macroaf.validate.ipca15 import carregar_configuracao, validar

JANELAS_MART = ["3m", "6m", "12m", "24m", "36m", "ano"]
CHAVE = ["mes", "chave_categoria"]
HISTORICO = [
    "registrado_em",
    "serie_id_antigo",
    "serie_id_novo",
    "categorias",
    "ligacao",
    "situacao",
]

# Dicionário de dados: fonte única do README e da ordem das colunas de cada arquivo.
# Valores possíveis das colunas categóricas: o README os lista e um teste confere com os dados.
VALORES = {
    "nivel_hierarquico": ["geral", "grupo", "subgrupo", "item", "subitem"],
    "serie_entrada": [
        "inicio dos dados",
        "novo",
        "fundido",
        "dividido",
        "renomeado (proposta rejeitada)",
        "fundido (proposta rejeitada)",
        "dividido (proposta rejeitada)",
    ],
    "serie_saida": [
        "em curso",
        "descontinuado",
        "fundido",
        "dividido",
        "renomeado (proposta rejeitada)",
        "fundido (proposta rejeitada)",
        "dividido (proposta rejeitada)",
    ],
    **{f"origem_{j}": ["oficial", "calculado"] for j in JANELAS_MART},
}

DICIONARIO: dict[str, dict] = {
    "categorias": {
        "descricao": "Uma linha por categoria publicada (tabela SIDRA e id). Dimensão dos outros arquivos.",
        "chave": ["chave_categoria"],
        "colunas": {
            "chave_categoria": "Identidade publicada pelo IBGE: `<tabela>.<id SIDRA>` (decisão 0006). Chave estável.",
            "tabela_sidra": "Tabela do SIDRA (uma por POF).",
            "codigo_sidra": "Id SIDRA da categoria nessa tabela.",
            "versao_pof": "POF que define a cesta e os pesos da tabela.",
            "codigo_ibge": "Código da categoria na classificação 315 (0 = índice geral).",
            "nome": "Nome da categoria como o IBGE publica.",
            "nivel_hierarquico": "Pelo número de dígitos do código.",
            "codigo_pai": "Código IBGE do nível de cima.",
            "grupo": "Código do grupo (1 dígito).",
            "subgrupo": "Código do subgrupo (2 dígitos).",
            "item": "Código do item (4 dígitos).",
            "serie_id": "Série longa a que a categoria pertence. Atributo de agrupamento: muda quando a revisão da harmonização junta ou separa séries (histórico em reference/historico_series_<indice>.csv).",
            "serie_nome": "Nome da categoria mais recente da série.",
            "serie_inicio": "Primeiro mês da série longa.",
            "serie_fim": "Último mês da série longa.",
            "serie_entrada": 'Como a série começa (o tipo da ligação; "(proposta rejeitada)" quando a revisão não aceitou a emenda).',
            "serie_saida": "Como a série termina (idem).",
        },
    },
    "mensal": {
        "descricao": "Uma linha por mês e categoria: valores oficiais do mês e indicadores da série longa.",
        "chave": CHAVE,
        "colunas": {
            "mes": "Mês de referência (AAAA-MM).",
            "chave_categoria": "Categoria (ver categorias).",
            "variacao_mensal": "Variação no mês, em %, como publicada (variável 355).",
            "peso": "Peso no mês, em % do índice geral, como publicado (357).",
            "variacao_acum_ano_publicada": "Acumulado no ano publicado (356), sem tratamento. Para o acumulado da série, use acumulados.acum_ano (A-023).",
            "variacao_acum_12m_publicada": "Acumulado em 12 meses publicado (1120) na tabela da categoria; vazio onde ela não publica (no geral, a 3065 publica: ver acumulados.acum_12m).",
            "indice_base_100": "Índice encadeado da série longa: 100 no mês anterior ao início da série (#41).",
            "contribuicao_pp": "Contribuição para a variação do geral no mês, em pontos percentuais (#43). Vazia nos subitens in natura da 1646, que entram pelo item (A-013).",
            "participacao_no_grupo": "% da soma das contribuições do mesmo nível no mesmo grupo. Vazia no geral e onde falta alguma contribuição no nível e grupo (A-025); nos grupos, sempre 100.",
            "sazonalidade_media": "Média da variação deste mês do ano nos 5 anos da série que terminam neste mês, inclusive (#44). Vazia sem 5 anos seguidos na série.",
            "sazonalidade_mediana": "Mediana da variação deste mês do ano nos mesmos 5 anos.",
            "cesta_variavel": "1 se este mês tem cesta variável (in natura da POF 1995-96, A-013).",
            "sazonalidade_cesta_variavel": "1 se a janela de 5 anos da sazonalidade contém mês com cesta variável.",
        },
    },
    "acumulados": {
        "descricao": "Uma linha por mês e categoria: acumulados por janela, oficial onde mede o mesmo que a série longa, calculado pelo índice onde falta ou onde o oficial não serve (#42).",
        "chave": CHAVE,
        "colunas": {
            "mes": "Mês de referência (AAAA-MM).",
            "chave_categoria": "Categoria (ver categorias).",
            **{
                f"acum_{j}": f"Acumulado em {j.replace('m', ' meses') if j != 'ano' else 'no ano'}, em %."
                for j in JANELAS_MART
            },
            **{f"origem_{j}": f"oficial ou calculado, para acum_{j}." for j in JANELAS_MART},
            "cesta_variavel_janelas": "Janelas que contêm mês com cesta variável, separadas por ponto e vírgula (A-013).",
        },
    },
    "contribuicoes": {
        "descricao": "Uma linha por mês e categoria: contribuição para o acumulado do geral em cada janela, em pontos percentuais (#43). Os subitens in natura da 1646 não têm contribuição (entram pelo item, A-013), então nenhuma janela aqui depende de cesta variável.",
        "chave": CHAVE,
        "colunas": {
            "mes": "Mês de referência (AAAA-MM).",
            "chave_categoria": "Categoria (ver categorias).",
            **{
                f"contrib_{j}": f"Contribuição para o acumulado do geral em {j.replace('m', ' meses') if j != 'ano' else 'no ano'}, em p.p."
                for j in JANELAS_MART
            },
        },
    },
    "difusao": {
        "descricao": "Uma linha por mês e recorte: porcentagem dos subitens com alta de preço (#44).",
        "chave": ["mes", "codigo_ibge"],
        "colunas": {
            "mes": "Mês de referência (AAAA-MM).",
            "codigo_ibge": "Recorte: 0 = índice geral; 1 a 9 = grupo.",
            "tabela_sidra": "Tabela do mês (a cesta é a da POF vigente).",
            "versao_pof": "POF da cesta.",
            "cesta_nova": "1 no primeiro mês de uma POF nova.",
            "subitens": "Subitens coletados (peso maior que zero).",
            "subitens_peso_zero": "Subitens com peso 0, fora da conta (A-026).",
            "positivos": "Subitens coletados com variação maior que zero.",
            "difusao_simples": "positivos / subitens, em %.",
            "difusao_ponderada": "Peso dos positivos / peso dos subitens, em %.",
        },
    },
}


def _chave_categoria(tabela: pd.Series, codigo: pd.Series) -> pd.Series:
    return tabela.astype(str) + "." + codigo.astype(str)


def montar_marts(
    dim: pd.DataFrame, longa: pd.DataFrame, ind: dict[str, pd.DataFrame]
) -> dict[str, pd.DataFrame]:
    """Os arquivos do mart, com as colunas do dicionário, na ordem e com o arredondamento finais."""
    longa = longa.assign(chave_categoria=_chave_categoria(longa.tabela_sidra, longa.codigo_sidra))
    series = longa.sort_values("mes").groupby("serie_id").agg(serie_nome=("nome", "last"))
    por_categoria = longa.drop_duplicates("chave_categoria").set_index("chave_categoria")
    categorias = dim.assign(chave_categoria=_chave_categoria(dim.tabela_sidra, dim.codigo_sidra))
    categorias = categorias.join(
        por_categoria[["serie_id", "inicio_serie", "fim_serie", "entrada", "saida"]],
        on="chave_categoria",
    ).join(series, on="serie_id")
    categorias = categorias.rename(
        columns={
            "inicio_serie": "serie_inicio",
            "fim_serie": "serie_fim",
            "entrada": "serie_entrada",
            "saida": "serie_saida",
        }
    )

    chave_serie = ["serie_id", "mes"]
    encadeado = ind["indice"].set_index(chave_serie)
    contrib = ind["contribuicoes"]
    mes_contrib = contrib[contrib.janela == "mes"].set_index(chave_serie)
    saz = ind["sazonalidade"].assign(mes=lambda d: d.ano_final.astype(str) + "-" + d.mes_do_ano)
    saz = saz.set_index(chave_serie)
    mensal = longa.set_index(chave_serie)
    mensal = mensal.assign(
        variacao_acum_ano_publicada=mensal.variacao_acum_ano,
        variacao_acum_12m_publicada=mensal.variacao_acum_12m,
        indice_base_100=encadeado.indice.round(6),
        cesta_variavel=encadeado.cesta_variavel.astype(int),
        contribuicao_pp=mes_contrib.contribuicao.round(6),
        participacao_no_grupo=mes_contrib.participacao_no_grupo.round(4),
        sazonalidade_media=saz.media.round(4),
        sazonalidade_mediana=saz.mediana.round(4),
        sazonalidade_cesta_variavel=saz.cesta_variavel.astype("Int64"),
    ).reset_index()
    acum = ind["acumulados"]
    larga = acum.pivot(index=chave_serie, columns="janela", values="acumulado").round(4)
    origem = acum.pivot(index=chave_serie, columns="janela", values="origem")
    marcadas = (
        acum[acum.cesta_variavel]
        .assign(ordem=lambda d: d.janela.map(JANELAS_MART.index))
        .sort_values("ordem")
        .groupby(chave_serie)
        .janela.agg(";".join)
    )
    acumulados = (
        longa.set_index(chave_serie)[["chave_categoria"]]
        .join(larga.add_prefix("acum_"))
        .join(origem.add_prefix("origem_"))
        .join(marcadas.rename("cesta_variavel_janelas"))
        .reset_index()
    )
    acumulados = acumulados.dropna(subset=[f"acum_{j}" for j in JANELAS_MART], how="all")
    larga_c = (
        contrib[contrib.janela != "mes"]
        .pivot(index=chave_serie, columns="janela", values="contribuicao")
        .round(6)
    )
    contribuicoes = (
        longa.set_index(chave_serie)[["chave_categoria"]]
        .join(larga_c.add_prefix("contrib_"))
        .reset_index()
        .dropna(subset=[f"contrib_{j}" for j in JANELAS_MART], how="all")
    )
    difusao = ind["difusao"].assign(
        cesta_nova=lambda d: d.cesta_nova.astype(int),
        difusao_simples=lambda d: d.difusao_simples.round(2),
        difusao_ponderada=lambda d: d.difusao_ponderada.round(2),
    )
    tabelas = {
        "categorias": categorias,
        "mensal": mensal,
        "acumulados": acumulados,
        "contribuicoes": contribuicoes,
        "difusao": difusao,
    }
    return {
        nome: tabela[list(DICIONARIO[nome]["colunas"])]
        .sort_values(DICIONARIO[nome]["chave"], key=_ordem)
        .reset_index(drop=True)
        for nome, tabela in tabelas.items()
    }


def _ordem(coluna: pd.Series) -> pd.Series:
    """Ordem fixa e natural: chave_categoria por tabela e id numéricos."""
    if coluna.name == "chave_categoria":
        partes = coluna.str.split(".", expand=True).astype(int)
        return partes[0] * 10**7 + partes[1]
    return coluna


def conferir(
    marts: dict[str, pd.DataFrame], longa: pd.DataFrame, ind: dict[str, pd.DataFrame], referencia
) -> list[str]:
    """Problemas que bloqueiam a publicação (vazia = pode publicar)."""
    problemas = []
    for nome, tabela in marts.items():
        if tabela.duplicated(DICIONARIO[nome]["chave"]).any():
            problemas.append(f"{nome}: chave {DICIONARIO[nome]['chave']} repetida")
    categorias = set(marts["categorias"].chave_categoria)
    for nome in ["mensal", "acumulados", "contribuicoes"]:
        if not set(marts[nome].chave_categoria) <= categorias:
            problemas.append(f"{nome}: categoria fora de categorias")
    if marts["categorias"].serie_id.isna().any():
        problemas.append("categorias: categoria sem série longa")
    geral = ind["indice"][ind["indice"].codigo_ibge == "0"].set_index("mes").indice.sort_index()
    oficial = referencia.set_index("mes").numero_indice.sort_index()
    if list(geral.index) != list(oficial.index) or geral.isna().any() or oficial.isna().any():
        problemas.append("índice geral e número-índice da referência têm meses diferentes")
    else:
        desvio = (geral / geral.iloc[0] * oficial.iloc[0] / oficial - 1).abs().max()
        if desvio > 1e-4:
            problemas.append(f"índice geral desvia {desvio:.6f} do número-índice da referência")
    contrib = ind["contribuicoes"]
    mes = contrib[contrib.janela == "mes"]
    grupos = mes[mes.nivel_hierarquico == "grupo"].groupby("mes").contribuicao.sum()
    do_geral = mes[mes.codigo_ibge == "0"].set_index("mes").contribuicao
    fora = (grupos - do_geral).abs() > limite_reconciliacao(longa) + 1e-9
    if fora.any():
        problemas.append(f"contribuições dos grupos não somam o geral em {int(fora.sum())} meses")
    for nome, tabela in marts.items():
        numericas = tabela.select_dtypes("number")
        if (numericas.abs() == float("inf")).any().any():
            problemas.append(f"{nome}: valor infinito")
    return problemas


def _csv(tabela: pd.DataFrame) -> bytes:
    texto = io.StringIO()
    tabela.to_csv(texto, index=False, lineterminator="\n")
    return texto.getvalue().encode("utf-8")


def atualizar_historico(
    anterior: pd.DataFrame | None, atual: pd.DataFrame, mapa: pd.DataFrame, registrado_em: str
) -> pd.DataFrame:
    """Mudanças de serie_id entre a publicação anterior e a atual (decisão 0006).

    A ligação registrada é a que chega à categoria de fronteira: a primeira (na ordem das POFs)
    das categorias que mudaram de série. Serve para fusão (a ligação aceita) e para divisão (a
    ligação que deixou de emendar), com a situação dela no mapa.
    """
    colunas = HISTORICO
    if anterior is None:
        return pd.DataFrame(columns=colunas)
    juntas = anterior[["chave_categoria", "serie_id"]].merge(
        atual[["chave_categoria", "serie_id", "versao_pof"]],
        on="chave_categoria",
        suffixes=("_antigo", "_novo"),
    )
    mudou = juntas[juntas.serie_id_antigo != juntas.serie_id_novo]
    if mudou.empty:
        return pd.DataFrame(columns=colunas)
    destinos = mapa.dropna(subset=["codigo_sidra_destino"]).assign(
        chave_categoria=lambda m: (
            m.tabela_destino.astype(int).astype(str)
            + "."
            + m.codigo_sidra_destino.astype(int).astype(str)
        ),
        ligacao=lambda m: [id_ligacao(r) for r in m.itertuples()],
    )
    linhas = []
    for (antigo, novo), grupo in mudou.groupby(["serie_id_antigo", "serie_id_novo"]):
        fronteira = grupo.sort_values("versao_pof").chave_categoria.iloc[0]
        ligacao = destinos[destinos.chave_categoria == fronteira]
        linhas.append(
            [
                registrado_em,
                antigo,
                novo,
                len(grupo),
                ligacao.ligacao.iloc[0] if len(ligacao) else "",
                ligacao.situacao.iloc[0] if len(ligacao) else "",
            ]
        )
    return pd.DataFrame(linhas, columns=colunas)


def _descricao_coluna(indice: Indice, coluna: str, original: str) -> str:
    """Rótulos por conceito; preserva o documento do piloto e seus exemplos históricos."""
    if indice.codigo == "ipca15":
        return original
    variaveis = {v.nome: v.codigo for v in indice.variaveis.values()}
    referencia = indice.tabelas_referencia[0].tabela
    textos = {
        "variacao_mensal": f"Variação mensal oficial, em % (variável {variaveis['variacao_mensal']}).",
        "peso": f"Peso mensal oficial, em % (variável {variaveis['peso']}).",
        "variacao_acum_ano_publicada": f"Acumulado no ano publicado ({variaveis['variacao_acum_ano']}), sem tratamento. Para a série longa, use acumulados.acum_ano.",
        "variacao_acum_12m_publicada": f"Acumulado em 12 meses publicado ({variaveis['variacao_acum_12m']}); vazio onde não disponível. Referência do geral: tabela {referencia}.",
        "contribuicao_pp": "Contribuição calculada para a variação mensal do geral, em pontos percentuais.",
        "cesta_variavel": "1 quando o mês está coberto por exceção estrutural documentada de cesta variável; 0 nos demais.",
        "sazonalidade_cesta_variavel": "1 quando a janela da sazonalidade contém mês com cesta variável documentada.",
        "cesta_variavel_janelas": "Janelas que contêm mês com cesta variável documentada, separadas por ponto e vírgula.",
    }
    return textos.get(coluna, original)


def _readme(indice: Indice, marts: dict[str, pd.DataFrame], ultimo_mes: str) -> str:
    partes = [
        f"# Marts do {indice.nome}",
        "",
        "Gerado por `uv run python -m macroaf.marts.publicar --indice "
        f"{indice.codigo}`. Não edite à mão.",
        "",
        f"Dados até **{ultimo_mes}**. CSV em UTF-8, separador vírgula, ponto decimal; no Power Query,",
        'leia com `Csv.Document(..., [Delimiter=",", Encoding=65001])` e tipe as colunas numéricas',
        'com a cultura `"en-US"`. Os nomes dos arquivos e das colunas são estáveis: colunas só são',
        "acrescentadas (decisões 0006 e 0007). Os relacionamentos usam `chave_categoria`, nunca",
        "`serie_id`, que muda quando a revisão da harmonização junta ou separa séries.",
        "",
        "Os valores oficiais passam como publicados. Os calculados são arredondados: 6 casas no",
        "índice e nas contribuições; 4 nos acumulados, na participação no grupo e na sazonalidade; 2 na",
        "difusão.",
        "",
        "Atualização: automática, quando o IBGE divulga um mês novo ou revisa um dos últimos meses",
        "(workflow `.github/workflows/atualizacao.yml`); `data/metadata.json` diz o último mês e a",
        "data da coleta.",
        "",
        "Metodologia: [`docs/METODOLOGIA.md`](../../docs/METODOLOGIA.md). Explicação passo a passo:",
        f"[`docs/transformacoes/{indice.codigo}.html`](../../docs/transformacoes/{indice.codigo}.html).",
    ]
    for nome, especificacao in DICIONARIO.items():
        tabela = marts[nome]
        partes += [
            "",
            f"## `{indice.codigo}_{nome}.csv`",
            "",
            (
                "Contribuições calculadas para o acumulado do geral, em pontos percentuais."
                if indice.codigo != "ipca15" and nome == "contribuicoes"
                else especificacao["descricao"]
            ),
            "",
            f"Chave: `{', '.join(especificacao['chave'])}`. Linhas: {len(tabela):,}.".replace(
                ",", "."
            ),
            "",
            "| Coluna | Descrição |",
            "|---|---|",
            *[
                f"| `{c}` | {_descricao_coluna(indice, c, d)}"
                + (f" Valores: {', '.join(f'`{v}`' for v in VALORES[c])}." if c in VALORES else "")
                + " |"
                for c, d in especificacao["colunas"].items()
            ],
        ]
    return "\n".join(partes) + "\n"


def publicar(indice: Indice, destino: Path = RAIZ) -> list[str]:
    """Monta, confere e grava os marts. Devolve os problemas; com problema, nada é gravado."""
    armazem = ArmazemRaw(indice.fonte)
    dim = montar_dim_classificacao(indice, armazem)
    fato = montar_fato(indice, armazem, dim)
    referencia = montar_referencia(indice, armazem)
    configuracao = carregar_configuracao(indice, armazem, dim)
    resultados, sentinelas = validar(fato, referencia, configuracao)
    problemas = [f"validação {r.validacao} falhou" for r in resultados if not r.ok]
    problemas += [f"sentinela {s.validacao} {s.codigo_ibge} mudou" for s in sentinelas.itertuples()]
    mapa = ler_mapa(indice)
    longa = montar_serie_longa(fato, dim, mapa)
    ind = calcular_indicadores(indice, longa, referencia)
    marts = montar_marts(dim, longa, ind)
    problemas += conferir(marts, longa, ind, referencia)
    if problemas:
        return problemas

    pasta = destino / "data" / "marts"
    pasta.mkdir(parents=True, exist_ok=True)
    ultimo_mes = longa.mes.max()
    caminho_categorias = pasta / f"{indice.codigo}_categorias.csv"
    anterior = pd.read_csv(caminho_categorias, dtype=str) if caminho_categorias.exists() else None
    historico_caminho = destino / "reference" / f"historico_series_{indice.codigo}.csv"
    manifesto = pd.DataFrame(armazem.ler_manifesto())
    manifesto = manifesto[manifesto.tabela.isin({str(t.tabela) for t in indice.tabelas})]
    manifesto = manifesto[manifesto.periodo != METADADOS]
    ultima_coleta = manifesto.data_coleta.max()
    historico = atualizar_historico(anterior, marts["categorias"], mapa, ultima_coleta[:10])
    if historico_caminho.exists():
        historico = pd.concat(
            [pd.read_csv(historico_caminho, dtype=str), historico.astype(str)], ignore_index=True
        )
    historico_caminho.write_bytes(_csv(historico))

    arquivos = {}
    for nome, tabela in marts.items():
        conteudo = _csv(tabela)
        (pasta / f"{indice.codigo}_{nome}.csv").write_bytes(conteudo)
        arquivos[f"{indice.codigo}_{nome}.csv"] = {
            "linhas": len(tabela),
            "colunas": list(tabela.columns),
            "sha256": hashlib.sha256(conteudo).hexdigest(),
        }
    dicionario = "README.md" if indice.codigo == "ipca15" else f"{indice.codigo}_README.md"
    (pasta / dicionario).write_text(_readme(indice, marts, ultimo_mes), encoding="utf-8")

    metadados = {
        "indice": indice.codigo,
        "nome": indice.nome,
        "ultimo_mes": ultimo_mes,
        "ultima_coleta": ultima_coleta,
        "tabelas": {
            str(t): {"inicio": g.periodo.min(), "fim": g.periodo.max()}
            for t, g in manifesto.groupby("tabela")
        },
        "validacoes": [
            {k: v for k, v in asdict(r).items() if k != "exemplos"} | {"ok": r.ok}
            for r in resultados
        ],
        "arquivos": arquivos,
    }
    caminho_meta = destino / "data" / "metadata.json"
    existente = json.loads(caminho_meta.read_text()) if caminho_meta.exists() else {}
    existente[indice.codigo] = metadados
    caminho_meta.write_text(
        json.dumps(existente, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monta, confere e publica os marts de um índice.")
    parser.add_argument("--indice", default="ipca15")
    args = parser.parse_args(argv)
    indice = carregar_catalogo().indices[args.indice]
    problemas = publicar(indice)
    if problemas:
        print("Publicação bloqueada:", file=sys.stderr)
        for p in problemas:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"Marts de {indice.codigo} publicados em data/marts/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
