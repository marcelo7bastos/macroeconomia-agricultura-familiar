"""API de metadados de agregados do IBGE (`servicodados.ibge.gov.br/api/v3/agregados`)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from macroaf.catalogo import Fonte
from macroaf.extract.cliente import Cliente, ErroFonte


@dataclass(frozen=True)
class Periodicidade:
    frequencia: str
    inicio: str  # AAAA-MM
    fim: str  # AAAA-MM


def periodo_sidra_para_iso(periodo: str | int) -> str:
    """`202609` (formato SIDRA) → `2026-09`."""
    texto = str(periodo)
    if len(texto) != 6 or not texto.isdigit():
        raise ErroFonte(f"período SIDRA inesperado: {periodo!r}")
    return f"{texto[:4]}-{texto[4:]}"


def periodo_iso_para_sidra(periodo: str) -> str:
    """`2026-09` → `202609`."""
    return periodo.replace("-", "")


def baixar_metadados(cliente: Cliente, fonte: Fonte, tabela: int) -> tuple[str, bytes, dict]:
    """Baixa os metadados de uma tabela; devolve URL, corpo original e conteúdo lido."""
    if not fonte.api_metadados:
        raise ErroFonte(f"fonte {fonte.codigo} sem api_metadados")
    url = f"{fonte.api_metadados}/{tabela}/metadados"
    conteudo = cliente.obter(url)
    try:
        metadados = json.loads(conteudo)
    except json.JSONDecodeError as erro:
        raise ErroFonte(f"{url}: resposta não é JSON: {conteudo[:200]!r}") from erro
    if not isinstance(metadados, dict) or "periodicidade" not in metadados:
        raise ErroFonte(f"{url}: metadados sem periodicidade")
    return url, conteudo, metadados


def periodicidade(metadados: dict) -> Periodicidade:
    try:
        bruta = metadados["periodicidade"]
        return Periodicidade(
            frequencia=bruta["frequencia"],
            inicio=periodo_sidra_para_iso(bruta["inicio"]),
            fim=periodo_sidra_para_iso(bruta["fim"]),
        )
    except (KeyError, TypeError) as erro:
        raise ErroFonte(f"periodicidade incompleta nos metadados: {erro}") from erro


def numero_categorias(metadados: dict, classificacao: int | None) -> int:
    """Categorias da classificação na tabela (1 se a tabela não tem classificação)."""
    if classificacao is None:
        return 1
    for item in metadados.get("classificacoes", []):
        if item.get("id") == classificacao:
            return len(item.get("categorias", []))
    raise ErroFonte(f"classificação {classificacao} ausente nos metadados")
