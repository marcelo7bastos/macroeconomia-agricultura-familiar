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


def obter_metadados(cliente: Cliente, fonte: Fonte, tabela: int) -> dict:
    if not fonte.api_metadados:
        raise ErroFonte(f"fonte {fonte.codigo} sem api_metadados")
    url = f"{fonte.api_metadados}/{tabela}/metadados"
    return json.loads(cliente.obter(url))


def periodicidade(metadados: dict) -> Periodicidade:
    bruta = metadados["periodicidade"]
    return Periodicidade(
        frequencia=bruta["frequencia"],
        inicio=periodo_sidra_para_iso(bruta["inicio"]),
        fim=periodo_sidra_para_iso(bruta["fim"]),
    )
