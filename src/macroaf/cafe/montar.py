"""Staging, validações e indicadores do piloto do café.

Do raw (BCB, FMI, Banco Mundial) e dos marts do IPCA até as duas tabelas do mart:

- `mensal`: uma linha por mês e série — preços internacionais convertidos para R$/saca de 60 kg
  pela PTAX média do mês e os subitens de café do IPCA, com índices na mesma base;
- `defasagens`: correlação entre a variação de cada preço internacional k meses antes e a do
  subitem principal do IPCA (descritiva, sem leitura causal).

Nada do IPCA é recalculado: variação mensal e número-índice vêm de `data/marts/ipca_mensal.csv`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from macroaf.cafe.configuracao import ConfiguracaoPrecos, Produto
from macroaf.cafe.fontes import COMPLETO, ler_banco_mundial, ler_fmi, ler_sgs
from macroaf.catalogo import RAIZ
from macroaf.extract.raw_arquivos import ArmazemArquivos
from macroaf.validate.ipca15 import Resultado

# 1 libra-peso = 0,45359237 kg (definição internacional de 1959): US¢/lb → US$/kg.
KG_POR_LIBRA = 0.45359237
KG_POR_SACA = 60
# A média mensal oficial do BCB tem 4 casas: a calculada difere no máximo meia unidade da última.
LIMITE_PTAX = 0.00005 + 1e-9
LIMITE_VARIACAO_FMI = 1e-6
CASAS = 6
CAMINHO_EXCECOES = RAIZ / "reference" / "excecoes_validacao_cafe.csv"


def usd_kg(valor: float | pd.Series, unidade: str):
    if unidade == "US$/kg":
        return valor
    if unidade == "US¢/lb":
        return valor / 100 / KG_POR_LIBRA
    raise ValueError(f"unidade sem conversão: {unidade}")


# --------------------------------------------------------------------------- staging


def montar_cambio(configuracao: ConfiguracaoPrecos, raiz=None) -> pd.DataFrame:
    """PTAX venda por mês: média calculada dos dias úteis e média oficial do BCB."""
    armazem = ArmazemArquivos("bcb_sgs", **({"raiz": raiz} if raiz else {}))
    diaria = [
        (dia, valor)
        for arquivo in armazem.vigentes(str(configuracao.cambio.serie_diaria)).values()
        for dia, valor in ler_sgs(armazem.ler(arquivo))
    ]
    oficial = [
        (dia, valor)
        for arquivo in armazem.vigentes(str(configuracao.cambio.serie_media_mensal)).values()
        for dia, valor in ler_sgs(armazem.ler(arquivo))
    ]
    dias = pd.DataFrame(diaria, columns=["data", "ptax"])
    if dias.data.duplicated().any():
        raise ValueError("PTAX diária com datas repetidas")
    dias["mes"] = pd.to_datetime(dias.data).dt.strftime("%Y-%m")
    calculada = dias.groupby("mes").ptax.agg(ptax_media="mean", dias_uteis="count")
    oficial = pd.DataFrame(oficial, columns=["data", "ptax_media_oficial"])
    oficial["mes"] = pd.to_datetime(oficial.data).dt.strftime("%Y-%m")
    return calculada.join(oficial.set_index("mes").ptax_media_oficial, how="outer").reset_index()


def montar_internacionais(
    configuracao: ConfiguracaoPrecos, produto: Produto, raiz=None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Preços internacionais como publicados (long) e a variação mensal oficial do FMI."""
    linhas, variacoes = [], []
    opcoes = {"raiz": raiz} if raiz else {}
    fmi = ArmazemArquivos("fmi_pcps", **opcoes).vigente(produto.codigo, COMPLETO)
    bm = ArmazemArquivos("banco_mundial_cmo", **opcoes).vigente(produto.codigo, COMPLETO)
    observacoes_fmi = ler_fmi(ArmazemArquivos.ler(fmi)) if fmi else []
    observacoes_bm = ler_banco_mundial(ArmazemArquivos.ler(bm)) if bm else []
    for serie in produto.internacionais:
        if serie.fonte == "fmi_pcps":
            for o in observacoes_fmi:
                if o.indicador != serie.codigo:
                    continue
                if o.transformacao == "USD":
                    linhas.append((o.mes, serie.id, serie.fonte, serie.unidade, o.valor))
                elif o.transformacao == "INDEX_PCH":
                    variacoes.append((o.mes, serie.id, o.valor))
        elif serie.fonte == "banco_mundial_cmo":
            for o in observacoes_bm:
                if o["codigo"] != serie.codigo:
                    continue
                if f"US{o['unidade']}" != serie.unidade:
                    raise ValueError(f"{serie.id}: unidade {o['unidade']} difere do catálogo")
                linhas.append((o["mes"], serie.id, serie.fonte, serie.unidade, float(o["valor"])))
    precos = pd.DataFrame(
        linhas, columns=["mes", "serie", "fonte", "unidade_original", "valor_original"]
    )
    faltam = {s.id for s in produto.internacionais} - set(precos.serie)
    if faltam:
        raise ValueError(f"séries internacionais sem dados no raw: {sorted(faltam)}")
    precos["preco_usd_kg"] = [
        usd_kg(v, u) for v, u in zip(precos.valor_original, precos.unidade_original, strict=True)
    ]
    variacao = pd.DataFrame(variacoes, columns=["mes", "serie", "variacao_mensal_oficial"])
    return precos.sort_values(["serie", "mes"], ignore_index=True), variacao


def montar_consumidor(produto: Produto, raiz=RAIZ) -> pd.DataFrame:
    """Subitens de café e índice geral do IPCA, lidos dos marts publicados (série longa)."""
    pasta = raiz / "data" / "marts"
    prefixo = produto.indice_consumidor
    categorias = pd.read_csv(pasta / f"{prefixo}_categorias.csv", dtype=str)
    mensal = pd.read_csv(pasta / f"{prefixo}_mensal.csv", dtype={"chave_categoria": str})
    partes = []
    for serie in [*produto.subitens, produto.deflator]:
        escolhidas = categorias[categorias.codigo_ibge == str(serie.codigo_ibge)]
        if escolhidas.serie_id.nunique() != 1:
            raise ValueError(
                f"{serie.id}: código {serie.codigo_ibge} com {escolhidas.serie_id.nunique()} "
                "séries longas; o piloto não emenda séries (harmonização do IPCA)"
            )
        linhas = mensal[mensal.chave_categoria.isin(escolhidas.chave_categoria)]
        if linhas.mes.duplicated().any():
            raise ValueError(f"{serie.id}: mais de uma linha por mês na série longa")
        partes.append(
            linhas[["mes", "chave_categoria", "variacao_mensal", "indice_base_100"]].assign(
                serie=serie.id,
                nome=escolhidas.serie_nome.iloc[0],
                variacao_acum_12m_publicada=linhas.variacao_acum_12m_publicada,
            )
        )
    return pd.concat(partes, ignore_index=True).sort_values(["serie", "mes"], ignore_index=True)


# --------------------------------------------------------------------------- validações


def _meses(inicio: str, fim: str) -> list[str]:
    return [p.strftime("%Y-%m") for p in pd.period_range(inicio, fim, freq="M")]


def ler_excecoes(caminho=CAMINHO_EXCECOES) -> pd.DataFrame:
    return pd.read_csv(caminho, dtype=str)


def validar(
    produto: Produto,
    cambio: pd.DataFrame,
    precos: pd.DataFrame,
    variacao_fmi: pd.DataFrame,
    consumidor: pd.DataFrame,
    excecoes: pd.DataFrame,
) -> list[Resultado]:
    resultados = []

    # 1. Câmbio: média calculada x média oficial, nos meses em que as duas existem.
    comum = cambio.dropna(subset=["ptax_media", "ptax_media_oficial"])
    diferenca = (comum.ptax_media - comum.ptax_media_oficial).abs()
    so_um_lado = len(cambio) - len(comum)
    resultados.append(
        Resultado(
            "ptax_media_mensal",
            verificados=len(comum),
            falhas=int((diferenca > LIMITE_PTAX).sum()) + so_um_lado,
            limite="0,00005 (arredondamento da média oficial a 4 casas)",
            ausentes=so_um_lado,
            maior_diferenca=round(float(diferenca.max()), 8),
            exemplos=comum[diferenca > LIMITE_PTAX].head(5).to_dict("records"),
        )
    )

    # 2. Continuidade: nenhum mês faltando em cada série, da base até o último mês dela.
    falhas, verificados, exemplos = 0, 0, []
    for serie, grupo in precos.groupby("serie"):
        esperados = _meses(produto.base_indice, grupo.mes.max())
        faltando = sorted(set(esperados) - set(grupo.mes))
        verificados += len(esperados)
        falhas += len(faltando)
        exemplos += [{"serie": serie, "mes": m} for m in faltando[:3]]
    meses_preco = sorted(precos[precos.mes >= produto.base_indice].mes.unique())
    sem_cambio = sorted(set(meses_preco) - set(cambio.dropna(subset=["ptax_media"]).mes))
    # O mês mais recente de uma fonte pode ainda não ter PTAX mensal fechada: só ele é tolerado.
    sem_cambio_falha = [m for m in sem_cambio if m != max(meses_preco)]
    for serie, grupo in consumidor.groupby("serie"):
        esperados = _meses(grupo.mes.min(), grupo.mes.max())
        faltando = sorted(set(esperados) - set(grupo.mes))
        verificados += len(esperados)
        falhas += len(faltando)
        exemplos += [{"serie": serie, "mes": m} for m in faltando[:3]]
    resultados.append(
        Resultado(
            "continuidade",
            verificados=verificados + len(meses_preco),
            falhas=falhas + len(sem_cambio_falha),
            limite="nenhum mês faltando; câmbio em todo mês com preço, salvo o último",
            ausentes=len(sem_cambio) - len(sem_cambio_falha),
            exemplos=exemplos + [{"serie": "ptax", "mes": m} for m in sem_cambio_falha[:3]],
        )
    )

    # 3. Valores positivos nos preços.
    negativos = precos[precos.valor_original <= 0]
    resultados.append(
        Resultado(
            "esquema",
            verificados=len(precos) + len(cambio),
            falhas=len(negativos) + int((cambio.ptax_media.dropna() <= 0).sum()),
            limite="preços e câmbio positivos; chave (mes, serie) única",
            exemplos=negativos.head(5).to_dict("records"),
        )
    )
    duplicadas = precos.duplicated(["mes", "serie"]).sum()
    resultados[-1].falhas += int(duplicadas)

    # 4. FMI: variação calculada do preço x variação mensal publicada pelo FMI.
    calculada = precos[precos.fonte == "fmi_pcps"].sort_values(["serie", "mes"]).copy()
    calculada["variacao"] = calculada.groupby("serie").valor_original.pct_change() * 100
    juntas = calculada.merge(variacao_fmi, on=["mes", "serie"], how="inner").dropna(
        subset=["variacao"]
    )
    diferenca = (juntas.variacao - juntas.variacao_mensal_oficial).abs()
    resultados.append(
        Resultado(
            "variacao_fmi",
            verificados=len(juntas),
            falhas=int((diferenca > LIMITE_VARIACAO_FMI).sum()),
            limite="1e-6 p.p. (mesma conta, precisão de máquina)",
            maior_diferenca=float(diferenca.max()) if len(juntas) else None,
            exemplos=juntas[diferenca > LIMITE_VARIACAO_FMI].head(5).to_dict("records"),
        )
    )

    # 5. Fontes com a mesma cotação: diferença relativa até o limite, com exceções contadas.
    largura = precos.pivot(index="mes", columns="serie", values="preco_usd_kg")
    listadas = excecoes[excecoes.validacao == "comparacao_fontes"]
    falhas, verificados, aplicadas, maior, exemplos = 0, 0, 0, 0.0, []
    for a, b in produto.comparacoes:
        par = largura[[a, b]].dropna()
        par = par[par.index >= produto.inicio]
        relativa = (par[a] / par[b] - 1).abs() * 100
        acima = set(relativa[relativa > produto.limite_comparacao_pct].index)
        conhecidas = set(listadas[(listadas.serie_a == a) & (listadas.serie_b == b)].mes)
        verificados += len(par)
        aplicadas += len(acima & conhecidas)
        maior = max(maior, float(relativa.max()))
        # Exceção contada exatamente: nova divergência ou exceção que deixou de existir falham.
        novas, sumidas = acima - conhecidas, conhecidas - acima
        falhas += len(novas) + len(sumidas)
        exemplos += [{"par": f"{a} x {b}", "mes": m, "situacao": "nova"} for m in sorted(novas)]
        exemplos += [{"par": f"{a} x {b}", "mes": m, "situacao": "sumiu"} for m in sorted(sumidas)]
    resultados.append(
        Resultado(
            "comparacao_fontes",
            verificados=verificados,
            falhas=falhas,
            limite=f"diferença relativa de {produto.limite_comparacao_pct:g}% em US$/kg",
            excecoes_aplicadas=aplicadas,
            maior_diferenca=round(maior, 6),
            exemplos=exemplos[:10],
        )
    )
    return resultados


# --------------------------------------------------------------------------- indicadores


@dataclass
class Montagem:
    cambio: pd.DataFrame
    precos: pd.DataFrame
    variacao_fmi: pd.DataFrame
    consumidor: pd.DataFrame
    resultados: list[Resultado]
    mensal: pd.DataFrame
    defasagens: pd.DataFrame


COLUNAS_MENSAL = [
    "mes",
    "serie",
    "nome",
    "lado",
    "fonte",
    "chave_categoria",
    "unidade_original",
    "valor_original",
    "ptax_media",
    "preco_usd_kg",
    "preco_brl_saca",
    "variacao_mensal",
    "variacao_acum_12m",
    "indice_base_100",
    "preco_real_brl_saca",
    "razao_consumidor_preco",
]
COLUNAS_DEFASAGENS = [
    "serie",
    "medida",
    "defasagem_meses",
    "correlacao",
    "observacoes",
    "inicio",
    "fim",
]


def calcular_mensal(
    produto: Produto, cambio: pd.DataFrame, precos: pd.DataFrame, consumidor: pd.DataFrame
) -> pd.DataFrame:
    nomes = {s.id: s.nome for s in produto.internacionais}
    ptax = cambio.set_index("mes").ptax_media
    deflator = consumidor[consumidor.serie == produto.deflator.id].set_index("mes").indice_base_100
    principal = (
        consumidor[consumidor.serie == produto.id_principal].set_index("mes").indice_base_100
    )
    ultimo_deflator = deflator.index.max()

    internacionais = precos[precos.mes >= produto.base_indice].copy()
    internacionais["ptax_media"] = internacionais.mes.map(ptax)
    internacionais["preco_brl_saca"] = (
        internacionais.preco_usd_kg * internacionais.ptax_media * KG_POR_SACA
    )
    internacionais = internacionais.dropna(subset=["preco_brl_saca"]).sort_values(
        ["serie", "mes"], ignore_index=True
    )
    por_serie = internacionais.groupby("serie").preco_brl_saca
    internacionais["variacao_mensal"] = por_serie.pct_change(fill_method=None) * 100
    internacionais["variacao_acum_12m"] = por_serie.pct_change(12, fill_method=None) * 100
    base = internacionais[internacionais.mes == produto.base_indice].set_index("serie")
    internacionais["indice_base_100"] = (
        internacionais.preco_brl_saca / internacionais.serie.map(base.preco_brl_saca) * 100
    )
    internacionais["preco_real_brl_saca"] = (
        internacionais.preco_brl_saca * deflator[ultimo_deflator] / internacionais.mes.map(deflator)
    )
    internacionais["razao_consumidor_preco"] = (
        internacionais.mes.map(principal) / internacionais.indice_base_100 * 100
    )
    internacionais = internacionais.assign(
        nome=internacionais.serie.map(nomes), lado="internacional", chave_categoria=pd.NA
    )

    ipca = consumidor.sort_values(["serie", "mes"], ignore_index=True).copy()
    # Acumulado em 12 meses pelo número-índice do próprio mart (com a base de 100 antes do início).
    indice = ipca.groupby("serie").indice_base_100
    anterior = indice.shift(12)
    anterior = anterior.where(anterior.notna() | (ipca.groupby("serie").cumcount() != 11), 100.0)
    ipca["variacao_acum_12m"] = (ipca.indice_base_100 / anterior - 1) * 100
    ipca = ipca.assign(
        lado="consumidor",
        fonte=produto.indice_consumidor,
        unidade_original=pd.NA,
        valor_original=np.nan,
        ptax_media=np.nan,
        preco_usd_kg=np.nan,
        preco_brl_saca=np.nan,
        preco_real_brl_saca=np.nan,
        razao_consumidor_preco=np.nan,
    )

    mensal = pd.concat([internacionais, ipca], ignore_index=True)
    mensal = mensal[mensal.mes >= produto.inicio][COLUNAS_MENSAL]
    numericas = mensal.select_dtypes("number").columns.drop(
        ["variacao_mensal", "indice_base_100", "valor_original", "ptax_media"]
    )
    mensal[numericas] = mensal[numericas].round(CASAS)
    # Valores publicados pelas fontes ficam como vieram; os calculados, com 6 casas.
    calculadas = mensal.lado == "internacional"
    for coluna in ["variacao_mensal", "indice_base_100"]:
        mensal.loc[calculadas, coluna] = mensal.loc[calculadas, coluna].round(CASAS)
    mensal["ptax_media"] = mensal.ptax_media.round(8)
    ordem = {
        s: i
        for i, s in enumerate(
            [s.id for s in produto.internacionais] + list(dict.fromkeys(consumidor.serie))
        )
    }
    return mensal.sort_values(
        ["mes", "serie"],
        key=lambda c: c.map(ordem) if c.name == "serie" else c,
        ignore_index=True,
    )


def calcular_defasagens(produto: Produto, mensal: pd.DataFrame) -> pd.DataFrame:
    """Correlação entre o preço internacional em t-k e o subitem principal do IPCA em t."""
    principal = mensal[mensal.serie == produto.id_principal].set_index("mes")
    linhas = []
    for serie in [s.id for s in produto.internacionais]:
        preco = mensal[mensal.serie == serie].set_index("mes")
        for medida in ["variacao_mensal", "variacao_acum_12m"]:
            x = preco[medida]
            for k in range(produto.defasagem_maxima + 1):
                deslocada = x.copy()
                deslocada.index = [
                    (pd.Period(m, "M") + k).strftime("%Y-%m") for m in deslocada.index
                ]
                par = pd.concat(
                    [deslocada.rename("x"), principal[medida].rename("y")], axis=1, join="inner"
                ).dropna()
                linhas.append(
                    {
                        "serie": serie,
                        "medida": medida,
                        "defasagem_meses": k,
                        "correlacao": round(float(par.x.corr(par.y)), CASAS),
                        "observacoes": len(par),
                        "inicio": par.index.min(),
                        "fim": par.index.max(),
                    }
                )
    return pd.DataFrame(linhas, columns=COLUNAS_DEFASAGENS)


def validar_acumulado_ipca(consumidor: pd.DataFrame, mensal: pd.DataFrame) -> Resultado:
    """Acumulado em 12 meses calculado pelo número-índice x variável oficial, onde ela existe.

    Limite analítico de arredondamento: meia unidade da casa publicada no acumulado (0,005) mais
    o efeito de 12 variações mensais publicadas com duas casas, cada uma com erro de até 0,005.
    """
    juntas = consumidor.merge(
        mensal[["mes", "serie", "variacao_acum_12m"]], on=["mes", "serie"]
    ).dropna(subset=["variacao_acum_12m", "variacao_acum_12m_publicada"])
    diferenca = (juntas.variacao_acum_12m - juntas.variacao_acum_12m_publicada).abs()
    limite = 0.005 + 12 * 0.005 * (1 + juntas.variacao_acum_12m.abs() / 100)
    return Resultado(
        "acumulado_12m_ipca",
        verificados=len(juntas),
        falhas=int((diferenca > limite).sum()),
        limite="0,005 + 12 x 0,005 x (1 + |acumulado|/100)",
        ausentes=int(mensal[mensal.lado == "consumidor"].variacao_acum_12m.notna().sum())
        - len(juntas),
        maior_diferenca=round(float(diferenca.max()), 6),
        exemplos=juntas[diferenca > limite].head(5).to_dict("records"),
    )


def montar(configuracao: ConfiguracaoPrecos, produto: Produto, raiz=None) -> Montagem:
    cambio = montar_cambio(configuracao, raiz)
    precos, variacao_fmi = montar_internacionais(configuracao, produto, raiz)
    consumidor = montar_consumidor(produto)
    resultados = validar(produto, cambio, precos, variacao_fmi, consumidor, ler_excecoes())
    mensal = calcular_mensal(produto, cambio, precos, consumidor)
    resultados.append(validar_acumulado_ipca(consumidor, mensal))
    defasagens = calcular_defasagens(produto, mensal)
    return Montagem(cambio, precos, variacao_fmi, consumidor, resultados, mensal, defasagens)
