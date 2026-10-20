import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.relatorios import graficos
from macroaf.relatorios.coleta import coletar, coletar_indicadores_planejados
from macroaf.relatorios.transformacoes import FEITOS, caminho_pagina, gerar, renderizar


@pytest.fixture(scope="module")
def pagina_gerada():
    return gerar("ipca15")


def test_pagina_de_transformacoes_esta_em_dia(pagina_gerada):
    # A página é gerada dos dados; se uma transformação mudou, regere no mesmo PR:
    #   uv run python -m macroaf.relatorios.transformacoes --indice ipca15
    gerada = pagina_gerada
    atual = caminho_pagina("ipca15").read_text(encoding="utf-8")
    assert atual == gerada, "docs/transformacoes/ipca15.html desatualizada; regere a página"


def test_pagina_traz_os_fatos_principais(pagina_gerada):
    html = pagina_gerada
    for trecho in [
        "<title>Transformações do IPCA-15</title>",
        "fato_ipca15",
        "Dúvidas em aberto",
        "A-012",
        'id="resultados"',
        'id="glossario"',
        "Os indicadores conferem com o IBGE",
        "4. Indicadores",
        "macroaf.indicators.sazonalidade",
    ]:
        assert trecho in html
    # Com os indicadores calculados, a página não pode dizer que nada foi calculado (decisão 0004).
    assert "Ainda não calculamos nenhuma inflação" not in html
    # Categorias que saem entram na troca em que saem, nunca numa transição "→ ?".
    assert "→ ?" not in html


def test_indicadores_feitos_existem_no_planejamento():
    # FEITOS usa o nome do indicador na seção 5.2; renomear lá sem mudar aqui perderia a marca.
    planejados = {i["indicador"] for i in coletar_indicadores_planejados()}
    assert set(FEITOS) <= planejados


def test_numeros_dos_graficos_com_virgula_e_sinal_de_menos():
    assert graficos._num(-0.5, 2) == "\u22120,50"
    assert graficos._num(10.0, 1, enxuto=True) == "10"
    assert graficos._num(10.05, 2, enxuto=True) == "10,05"
    assert graficos._mes("2026-09") == "set/2026"


def test_barra_negativa_nao_cobre_o_nome():
    svg = graficos.barras("teste", ["a", "b"], [1.0, -1.0])
    assert svg.count("<rect") == 2
    assert "\u22121,00" in svg


def test_numeros_da_pagina_dentro_dos_limites_das_conferencias():
    # As conferências da página saem dos dados; os limites são os dos testes dos indicadores.
    f = coletar(carregar_catalogo().indices["ipca15"])
    c = f["resultados"]["conferencias"]
    assert c["desvio_1117"] <= 0.01
    assert c["grupos_mes"] < 0.01
    assert c["erros_3065"] == 4
    # O texto do rastreio sai dos dados: muda se a revisão emendar as séries do leite (#32).
    series = {r["indicadores"]["serie_id"] for r in f["rastreios"]}
    assert len(series) == 2
    assert f"atravessa {len(series)} séries longas" in renderizar(f)
