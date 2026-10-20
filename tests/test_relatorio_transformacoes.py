from macroaf.relatorios.coleta import coletar_indicadores_planejados
from macroaf.relatorios.transformacoes import FEITOS, caminho_pagina, gerar


def test_pagina_de_transformacoes_esta_em_dia():
    # A página é gerada dos dados; se uma transformação mudou, regere no mesmo PR:
    #   uv run python -m macroaf.relatorios.transformacoes --indice ipca15
    gerada = gerar("ipca15")
    atual = caminho_pagina("ipca15").read_text(encoding="utf-8")
    assert atual == gerada, "docs/transformacoes/ipca15.html desatualizada; regere a página"


def test_pagina_traz_os_fatos_principais():
    html = gerar("ipca15")
    for trecho in [
        "<title>Transformações do IPCA-15</title>",
        "fato_ipca15",
        "Dúvidas em aberto",
        "A-012",
    ]:
        assert trecho in html


def test_indicadores_feitos_existem_no_planejamento():
    # FEITOS usa o nome do indicador na seção 5.2; renomear lá sem mudar aqui perderia a marca.
    planejados = {i["indicador"] for i in coletar_indicadores_planejados()}
    assert set(FEITOS) <= planejados
