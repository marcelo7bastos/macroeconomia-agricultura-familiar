"""Todos os indicadores de um índice, calculados a partir da série longa (#41 a #44)."""

from __future__ import annotations

import pandas as pd

from macroaf.catalogo import Indice
from macroaf.indicators.acumulados import montar_acumulados
from macroaf.indicators.contribuicoes import montar_contribuicoes
from macroaf.indicators.difusao import montar_difusao
from macroaf.indicators.indice import marcar_cesta_variavel, montar_indice
from macroaf.indicators.sazonalidade import montar_sazonalidade
from macroaf.validate.ipca15 import carregar_excecoes


def calcular_indicadores(
    indice: Indice, longa: pd.DataFrame, referencia: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    """Índice encadeado, acumulados, contribuições, difusão e sazonalidade, cada um uma vez."""
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
