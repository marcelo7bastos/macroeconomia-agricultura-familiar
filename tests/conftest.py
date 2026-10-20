"""Dados reais preparados uma vez; cada módulo recebe cópias para trabalhar isoladamente.

Os testes de publicação e de relatórios continuam executando o fluxo completo.
Fixtures de sessão não dependem de staging nem de cache persistido entre execuções.
"""

import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.transform.classificacao import montar_dim_classificacao
from macroaf.transform.harmonizacao import ler_mapa, montar_serie_longa
from macroaf.transform.ipca15 import montar_fato, montar_referencia


@pytest.fixture(scope="session")
def _indice():
    return carregar_catalogo().indices["ipca15"]


@pytest.fixture(scope="session")
def _dim(_indice):
    return montar_dim_classificacao(_indice, ArmazemRaw(_indice.fonte))


@pytest.fixture(scope="session")
def _fato(_indice, _dim):
    return montar_fato(_indice, ArmazemRaw(_indice.fonte), _dim)


@pytest.fixture(scope="session")
def _referencia(_indice):
    return montar_referencia(_indice, ArmazemRaw(_indice.fonte))


@pytest.fixture(scope="session")
def _longa(_indice, _dim, _fato):
    return montar_serie_longa(_fato, _dim, ler_mapa(_indice))


@pytest.fixture(scope="module")
def dados_dim(_dim):
    return _dim.copy(deep=True)


@pytest.fixture(scope="module")
def dados_fato(_fato):
    return _fato.copy(deep=True)


@pytest.fixture(scope="module")
def dados_referencia(_referencia):
    return _referencia.copy(deep=True)


@pytest.fixture(scope="module")
def dados_longa(_longa):
    return _longa.copy(deep=True)
