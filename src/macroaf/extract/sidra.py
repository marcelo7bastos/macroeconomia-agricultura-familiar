"""API de valores do SIDRA (`apisidra.ibge.gov.br/values`)."""

from __future__ import annotations

import json

from macroaf.catalogo import Fonte, Tabela
from macroaf.extract.cliente import Cliente, ErroFonte
from macroaf.extract.ibge_metadados import periodo_iso_para_sidra


def url_valores(fonte: Fonte, tabela: Tabela, periodo: str) -> str:
    """URL de um mês: nível Brasil, variáveis do catálogo e todas as categorias."""
    variaveis = ",".join(str(v) for v in tabela.variaveis)
    url = (
        f"{fonte.api_valores}/t/{tabela.tabela}/n1/all/v/{variaveis}"
        f"/p/{periodo_iso_para_sidra(periodo)}"
    )
    if tabela.classificacao is not None:
        url += f"/c{tabela.classificacao}/all"
    return url


def registros(conteudo: bytes) -> list[dict]:
    """Registros de uma resposta da API de valores, sem a linha de cabeçalho."""
    try:
        dados = json.loads(conteudo)
    except json.JSONDecodeError as erro:
        raise ErroFonte(f"resposta não é JSON: {conteudo[:200]!r}") from erro
    if not isinstance(dados, list) or not dados:
        raise ErroFonte("resposta da API SIDRA sem a linha de cabeçalho")
    return dados[1:]


def _coluna(cabecalho: dict, rotulo: str, url: str) -> str:
    for chave, valor in cabecalho.items():
        if valor == rotulo:
            return chave
    raise ErroFonte(f"{url}: cabeçalho sem a coluna {rotulo!r}")


def baixar_mes(
    cliente: Cliente,
    fonte: Fonte,
    tabela: Tabela,
    periodo: str,
    registros_esperados: int | None = None,
) -> tuple[str, bytes]:
    """Baixa um mês de uma tabela e confere período, variáveis e, se informado, o tamanho."""
    url = url_valores(fonte, tabela, periodo)
    conteudo = cliente.obter(url)
    linhas = registros(conteudo)
    if not linhas:
        raise ErroFonte(f"{url}: resposta sem registros")
    cabecalho = json.loads(conteudo)[0]
    coluna_mes = _coluna(cabecalho, "Mês (Código)", url)
    coluna_variavel = _coluna(cabecalho, "Variável (Código)", url)

    periodos = {linha.get(coluna_mes) for linha in linhas}
    if periodos != {periodo_iso_para_sidra(periodo)}:
        raise ErroFonte(f"{url}: períodos inesperados na resposta: {sorted(periodos)}")
    variaveis = {linha.get(coluna_variavel) for linha in linhas}
    if variaveis != {str(v) for v in tabela.variaveis}:
        raise ErroFonte(f"{url}: variáveis inesperadas na resposta: {sorted(variaveis)}")
    if registros_esperados is not None and len(linhas) != registros_esperados:
        raise ErroFonte(f"{url}: {len(linhas)} registros, esperados {registros_esperados}")
    return url, conteudo
