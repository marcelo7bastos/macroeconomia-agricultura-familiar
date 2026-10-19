import gzip
import json

import httpx
import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.extract.atualizar import (
    CatalogoDivergente,
    atualizar_indice,
    divergencias,
    meses_entre,
    planejar,
)
from macroaf.extract.cliente import Cliente, ErroFonte
from macroaf.extract.ibge_metadados import Periodicidade
from macroaf.extract.raw import ArmazemRaw
from macroaf.extract.sidra import baixar_mes, url_valores

CATALOGO = carregar_catalogo()
IPCA15 = CATALOGO.indices["ipca15"]
FONTE = CATALOGO.fontes["ibge_sidra"]
TABELAS = {t.tabela: t for t in IPCA15.tabelas}
CABECALHO = {"NC": "Nível Territorial (Código)", "V": "Valor", "D3C": "Mês (Código)"}


def resposta_valores(periodo_sidra: str, valores=("0.70", "0.10")) -> bytes:
    linhas = [
        {"NC": "1", "V": v, "D2C": "355", "D3C": periodo_sidra, "D4C": str(7169 + i)}
        for i, v in enumerate(valores)
    ]
    return json.dumps([CABECALHO, *linhas], ensure_ascii=False).encode()


def cliente_falso(rotas, chamadas=None) -> Cliente:
    def responder(requisicao: httpx.Request) -> httpx.Response:
        url = str(requisicao.url)
        if chamadas is not None:
            chamadas.append(url)
        for trecho, resposta in rotas.items():
            if trecho in url:
                return resposta(url) if callable(resposta) else resposta
        return httpx.Response(404)

    return Cliente(httpx.Client(transport=httpx.MockTransport(responder)), pausa=0, espera_minima=0)


def metadados(inicio: str, fim: str) -> httpx.Response:
    return httpx.Response(
        200, json={"periodicidade": {"frequencia": "mensal", "inicio": inicio, "fim": fim}}
    )


# --- planejamento ---------------------------------------------------------------------------


def test_meses_entre_atravessa_o_ano():
    assert meses_entre("2019-11", "2020-02") == ["2019-11", "2019-12", "2020-01", "2020-02"]


def test_planejar_tabela_fechada_baixa_so_o_que_falta_e_nao_revisa():
    publicada = Periodicidade("mensal", "2000-05", "2006-07")
    plano = planejar(TABELAS[1646], publicada, salvos=meses_entre("2000-05", "2006-05"))
    assert plano.novos == ["2006-06", "2006-07"]
    assert plano.revisao == []


def test_planejar_tabela_aberta_revisa_os_ultimos_meses():
    publicada = Periodicidade("mensal", "2020-02", "2026-09")
    plano = planejar(TABELAS[7062], publicada, salvos=meses_entre("2020-02", "2026-08"))
    assert plano.novos == ["2026-09"]
    assert plano.revisao == ["2026-06", "2026-07", "2026-08"]


def test_planejar_respeita_o_limite_ate():
    publicada = Periodicidade("mensal", "2020-02", "2026-09")
    plano = planejar(TABELAS[7062], publicada, salvos=[], ate="2020-04")
    assert plano.novos == ["2020-02", "2020-03", "2020-04"]


def test_divergencias_entre_catalogo_e_metadados():
    assert divergencias(TABELAS[1705], Periodicidade("mensal", "2012-02", "2020-01")) == []
    problemas = divergencias(TABELAS[1705], Periodicidade("mensal", "2012-01", "2020-02"))
    assert len(problemas) == 2
    # Tabela aberta: o fim publicado avança sem ser divergência.
    assert divergencias(TABELAS[7062], Periodicidade("mensal", "2020-02", "2030-01")) == []


# --- API de valores -------------------------------------------------------------------------


def test_url_valores_com_e_sem_classificacao():
    assert url_valores(FONTE, TABELAS[7062], "2026-09") == (
        "https://apisidra.ibge.gov.br/values/t/7062/n1/all/v/355,356,1120,357/p/202609/c315/all"
    )
    assert url_valores(FONTE, TABELAS[3065], "2026-09").endswith("/p/202609")


@pytest.mark.parametrize(
    ("corpo", "mensagem"),
    [
        (json.dumps([CABECALHO]).encode(), "sem registros"),
        (resposta_valores("202608"), "períodos inesperados"),
        (b"Tabela inexistente", "não é JSON"),
    ],
)
def test_baixar_mes_rejeita_resposta_inutil(corpo, mensagem):
    cliente = cliente_falso({"/values/": httpx.Response(200, content=corpo)})
    with pytest.raises(ErroFonte, match=mensagem):
        baixar_mes(cliente, FONTE, TABELAS[7062], "2026-09")


def test_erro_400_do_sidra_vira_erro_definitivo_sem_retentativa():
    chamadas = []
    cliente = cliente_falso({"/values/": httpx.Response(400, text="Limite excedido")}, chamadas)
    with pytest.raises(ErroFonte, match="Limite excedido"):
        cliente.obter("https://apisidra.ibge.gov.br/values/t/1")
    assert len(chamadas) == 1


def test_cliente_tenta_de_novo_em_erro_do_servidor():
    respostas = iter([httpx.Response(503), httpx.Response(500), httpx.Response(200, content=b"ok")])
    cliente = cliente_falso({"/": lambda _url: next(respostas)})
    assert cliente.obter("https://exemplo.gov.br/") == b"ok"


# --- camada raw -----------------------------------------------------------------------------


def test_raw_salva_compactado_com_hash_do_original(tmp_path):
    armazem = ArmazemRaw("ibge_sidra", raiz=tmp_path)
    conteudo = resposta_valores("202609")
    entrada = armazem.salvar(7062, "2026-09", "https://x", conteudo)

    arquivo = tmp_path / "ibge_sidra" / "7062" / "202609.json.gz"
    assert gzip.decompress(arquivo.read_bytes()) == conteudo
    assert entrada.revisao == 1
    assert entrada.n_registros == 2
    assert armazem.periodos(7062) == ["2026-09"]
    assert armazem.ler_manifesto()[0]["sha256"] == entrada.sha256


def test_raw_compactacao_e_deterministica(tmp_path):
    conteudo = resposta_valores("202609")
    ArmazemRaw("a", raiz=tmp_path).salvar(7062, "2026-09", "u", conteudo)
    ArmazemRaw("b", raiz=tmp_path).salvar(7062, "2026-09", "u", conteudo)
    primeiro = (tmp_path / "a" / "7062" / "202609.json.gz").read_bytes()
    assert primeiro == (tmp_path / "b" / "7062" / "202609.json.gz").read_bytes()


def test_raw_mesma_coleta_em_outra_ordem_nao_gera_revisao(tmp_path):
    armazem = ArmazemRaw("ibge_sidra", raiz=tmp_path)
    dados = json.loads(resposta_valores("202609"))
    armazem.salvar(7062, "2026-09", "u", json.dumps(dados).encode())
    invertido = [dados[0], *reversed(dados[1:])]
    assert armazem.salvar(7062, "2026-09", "u", json.dumps(invertido).encode()) is None
    assert len(armazem.ler_manifesto()) == 1


def test_raw_conteudo_alterado_vira_revisao_sem_apagar_o_anterior(tmp_path):
    armazem = ArmazemRaw("ibge_sidra", raiz=tmp_path)
    armazem.salvar(7062, "2026-09", "u", resposta_valores("202609", ("0.70", "0.10")))
    entrada = armazem.salvar(7062, "2026-09", "u", resposta_valores("202609", ("0.71", "0.10")))

    assert entrada.revisao == 2
    pasta = tmp_path / "ibge_sidra" / "7062"
    assert sorted(p.name for p in pasta.iterdir()) == ["202609.json.gz", "202609.r2.json.gz"]
    assert armazem.vigente(7062, "2026-09").name == "202609.r2.json.gz"


# --- orquestração ---------------------------------------------------------------------------


def _rotas_ipca15(valores_7062=("0.70", "0.10")):
    return {
        "/agregados/7062/metadados": metadados("202002", "202004"),
        "/agregados/3065/metadados": metadados("200005", "202004"),
        "/t/7062/": lambda url: httpx.Response(
            200, content=resposta_valores(url.split("/p/")[1][:6], valores_7062)
        ),
    }


def test_atualizar_baixa_o_que_falta_e_depois_so_revisa(tmp_path):
    armazem = ArmazemRaw("ibge_sidra", raiz=tmp_path)
    chamadas = []
    relatorio = atualizar_indice(
        CATALOGO,
        IPCA15,
        cliente_falso(_rotas_ipca15(), chamadas),
        armazem,
        tabelas={7062},
        log=lambda _m: None,
    )
    assert relatorio.novos == {7062: ["2020-02", "2020-03", "2020-04"]}
    assert armazem.periodos(7062) == ["2020-02", "2020-03", "2020-04"]

    # Segunda execução, sem mês novo e com o IBGE revisando um valor: só a janela de revisão.
    relatorio = atualizar_indice(
        CATALOGO,
        IPCA15,
        cliente_falso(_rotas_ipca15(("0.70", "0.11"))),
        armazem,
        tabelas={7062},
        log=lambda _m: None,
    )
    assert relatorio.total_novos == 0
    assert relatorio.revisados == {7062: ["2020-02", "2020-03", "2020-04"]}


def test_atualizar_em_modo_verificar_nao_baixa_valores(tmp_path):
    chamadas = []
    relatorio = atualizar_indice(
        CATALOGO,
        IPCA15,
        cliente_falso(_rotas_ipca15(), chamadas),
        ArmazemRaw("ibge_sidra", raiz=tmp_path),
        verificar=True,
        tabelas={7062, 3065},
        log=lambda _m: None,
    )
    assert relatorio.total_novos == 3 + 240
    assert not any("/values/" in url for url in chamadas)


def test_atualizar_interrompe_se_catalogo_diverge_dos_metadados(tmp_path):
    rotas = _rotas_ipca15() | {"/agregados/7062/metadados": metadados("202001", "202004")}
    chamadas = []
    with pytest.raises(CatalogoDivergente, match="7062"):
        atualizar_indice(
            CATALOGO,
            IPCA15,
            cliente_falso(rotas, chamadas),
            ArmazemRaw("ibge_sidra", raiz=tmp_path),
            tabelas={7062},
            log=lambda _m: None,
        )
    assert not any("/values/" in url for url in chamadas)
