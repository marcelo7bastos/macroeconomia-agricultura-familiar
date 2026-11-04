"""Piloto do café (#62): leitores das fontes, raw, validações, indicadores e publicação."""

import gzip
import hashlib
import io
import json
import shutil
from dataclasses import replace

import numpy as np
import openpyxl
import pandas as pd
import pytest
import yaml

from macroaf.cafe import fontes
from macroaf.cafe import publicar as modulo
from macroaf.cafe.configuracao import carregar
from macroaf.cafe.montar import (
    KG_POR_SACA,
    calcular_mensal,
    ler_excecoes,
    montar,
    usd_kg,
    validar,
)
from macroaf.cafe.publicar import DICIONARIO, conferir, publicar
from macroaf.catalogo import RAIZ, ErroCatalogo
from macroaf.extract.raw_arquivos import ArmazemArquivos

CONFIGURACAO = carregar()
CAFE = CONFIGURACAO.produtos["cafe"]


@pytest.fixture(scope="module")
def montagem():
    return montar(CONFIGURACAO, CAFE)


# --------------------------------------------------------------------------- leitores


def test_conversao_de_unidade():
    # 100 US¢/lb = 1 US$/lb = 2,20462262... US$/kg (1 lb = 0,45359237 kg, exato).
    assert usd_kg(100.0, "US¢/lb") == pytest.approx(2.2046226218)
    assert usd_kg(7.4, "US$/kg") == 7.4
    with pytest.raises(ValueError):
        usd_kg(1.0, "R$/saca")


def test_url_do_sgs_cobre_o_mes_inteiro():
    url = fontes.url_sgs("https://x/bcdata.sgs.{serie}/dados", 1, 2024, 2)
    assert url.endswith("sgs.1/dados?formato=json&dataInicial=01/02/2024&dataFinal=29/02/2024")


def test_ler_sgs_recusa_formato_desconhecido():
    assert fontes.ler_sgs(b'[{"data":"01/09/2026","valor":"5.1570"}]')[0][1] == 5.157
    with pytest.raises(fontes.ErroFormato):
        fontes.ler_sgs(b'{"erro": "intervalo"}')
    with pytest.raises(fontes.ErroFormato):
        fontes.ler_sgs(b'[{"data":"01/09/2026","valor":"5.1","x":1}]')


XML_FMI = b"""<?xml version='1.0'?><m:StructureSpecificData xmlns:m="urn:m"><m:DataSet>
<Series COUNTRY="G001" INDICATOR="PCOFFOTM" DATA_TRANSFORMATION="USD" FREQUENCY="M" SCALE="0">
<Obs TIME_PERIOD="2026-M08" OBS_VALUE="360.5"/><Obs TIME_PERIOD="2026-M09" OBS_VALUE="330.1"/>
</Series></m:DataSet></m:StructureSpecificData>"""


def test_ler_fmi():
    observacoes = fontes.ler_fmi(XML_FMI)
    assert [(o.indicador, o.transformacao, o.mes, o.valor) for o in observacoes] == [
        ("PCOFFOTM", "USD", "2026-08", 360.5),
        ("PCOFFOTM", "USD", "2026-09", 330.1),
    ]
    with pytest.raises(fontes.ErroFormato):
        fontes.ler_fmi(XML_FMI.replace(b'SCALE="0"', b'SCALE="3"'))
    with pytest.raises(fontes.ErroFormato):
        fontes.ler_fmi(XML_FMI.replace(b"2026-M09", b"2026-09"))


def test_chave_do_fmi_pede_preco_e_variacao_oficial():
    series = [s for s in CAFE.internacionais if s.fonte == "fmi_pcps"]
    assert fontes.chave_fmi(series) == "G001.PCOFFOTM+PCOFFROB.USD+INDEX_PCH.M"


def test_link_do_banco_mundial_exige_um_unico_link():
    arquivo = "CMO-Historical-Data-Monthly.xlsx"
    um = f'<a href="https://thedocs.worldbank.org/en/doc/abc/related/{arquivo}">x</a>'.encode()
    assert fontes.link_banco_mundial(um, arquivo).endswith("/abc/related/" + arquivo)
    assert fontes.link_banco_mundial(um + um, arquivo)  # o mesmo link repetido conta uma vez
    with pytest.raises(fontes.ErroFormato):
        fontes.link_banco_mundial(b"<html></html>", arquivo)
    outro = um.replace(b"/abc/", b"/def/")
    with pytest.raises(fontes.ErroFormato):
        fontes.link_banco_mundial(um + outro, arquivo)


def _planilha(linhas):
    livro = openpyxl.Workbook()
    aba = livro.active
    aba.title = "Monthly Prices"
    for linha in linhas:
        aba.append(linha)
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()


def test_recorte_do_banco_mundial():
    planilha = _planilha(
        [
            ["World Bank Commodity Price Data (The Pink Sheet)"],
            ["Updated on November 03, 2026"],
            [None, "Crude oil", "Coffee, Arabica", "Coffee, Robusta"],
            [None, "($/bbl)", "($/kg)", "($/kg)"],
            ["2026M09", 70.1, 7.26, 3.69],
            ["2026M10", 69.0, 7.4, "…"],
        ]
    )
    recorte, atualizacao = fontes.recortar_banco_mundial(
        planilha, "Monthly Prices", ["Coffee, Arabica", "Coffee, Robusta"]
    )
    assert atualizacao == "Updated on November 03, 2026"
    linhas = fontes.ler_banco_mundial(recorte)
    assert [(lin["mes"], lin["codigo"], lin["unidade"], lin["valor"]) for lin in linhas] == [
        ("2026-09", "Coffee, Arabica", "$/kg", "7.26"),
        ("2026-09", "Coffee, Robusta", "$/kg", "3.69"),
        ("2026-10", "Coffee, Arabica", "$/kg", "7.4"),
    ]
    with pytest.raises(fontes.ErroFormato):
        fontes.recortar_banco_mundial(planilha, "Monthly Prices", ["Coffee, Other"])
    with pytest.raises(fontes.ErroFormato):
        fontes.recortar_banco_mundial(planilha, "Outra aba", ["Coffee, Arabica"])


# --------------------------------------------------------------------------- raw


def test_raw_grava_so_quando_o_canonico_muda(tmp_path):
    armazem = ArmazemArquivos("fonte", raiz=tmp_path)
    primeira = armazem.salvar("cafe", "completo", "xml", "u", XML_FMI, fontes.ler_fmi, 2)
    assert primeira and primeira.revisao == 1
    # Mesmo conteúdo com outro cabeçalho: nada novo.
    outro_cabecalho = XML_FMI.replace(b"<m:DataSet>", b"<m:Header>x</m:Header><m:DataSet>")
    assert (
        armazem.salvar("cafe", "completo", "xml", "u", outro_cabecalho, fontes.ler_fmi, 2) is None
    )
    revisto = XML_FMI.replace(b"330.1", b"331.0")
    segunda = armazem.salvar("cafe", "completo", "xml", "u", revisto, fontes.ler_fmi, 2)
    assert segunda.revisao == 2 and segunda.arquivo == "cafe/completo.r2.xml.gz"
    assert armazem.ler(armazem.vigente("cafe", "completo")) == revisto
    assert [lin["revisao"] for lin in armazem.ler_manifesto()] == ["1", "2"]


@pytest.mark.parametrize("fonte", ["bcb_sgs", "fmi_pcps", "banco_mundial_cmo"])
def test_raw_do_cafe_confere_com_o_manifesto(fonte):
    armazem = ArmazemArquivos(fonte)
    manifesto = {linha["arquivo"]: linha for linha in armazem.ler_manifesto()}
    arquivos = sorted(
        p.relative_to(armazem.diretorio).as_posix() for p in armazem.diretorio.glob("*/*.gz")
    )
    assert arquivos, f"raw de {fonte} vazio"
    assert sorted(manifesto) == arquivos
    for arquivo in arquivos:
        conteudo = gzip.decompress((armazem.diretorio / arquivo).read_bytes())
        assert hashlib.sha256(conteudo).hexdigest() == manifesto[arquivo]["sha256"], arquivo


# --------------------------------------------------------------------------- configuração


def test_configuracao_recusa_base_fora_do_mes_anterior(tmp_path):
    texto = (RAIZ / "config" / "precos.yaml").read_text(encoding="utf-8")
    errado = tmp_path / "precos.yaml"
    errado.write_text(texto.replace("base_indice: 2006-06", "base_indice: 2006-05"), "utf-8")
    with pytest.raises(ErroCatalogo, match="mês anterior"):
        carregar(errado)
    errado.write_text(texto.replace("unidade: US$/kg\n", "unidade: R$/kg\n", 1), "utf-8")
    with pytest.raises(ErroCatalogo, match="unidade"):
        carregar(errado)


# --------------------------------------------------------------------------- validações


def test_todas_as_validacoes_passam(montagem):
    falhas = {r.validacao: r.exemplos for r in montagem.resultados if not r.ok}
    assert falhas == {}
    nomes = {r.validacao for r in montagem.resultados}
    assert nomes == {
        "ptax_media_mensal",
        "continuidade",
        "esquema",
        "variacao_fmi",
        "comparacao_fontes",
        "acumulado_12m_ipca",
    }


def test_ptax_calculada_reproduz_a_media_oficial(montagem):
    cambio = montagem.cambio.dropna()
    assert len(cambio) >= 250
    assert (cambio.ptax_media - cambio.ptax_media_oficial).abs().max() <= 0.00005 + 1e-9


def _validacao(montagem, nome, **mudancas):
    argumentos = {
        "produto": CAFE,
        "cambio": montagem.cambio,
        "precos": montagem.precos,
        "variacao_fmi": montagem.variacao_fmi,
        "consumidor": montagem.consumidor,
        "excecoes": ler_excecoes(),
    } | mudancas
    return next(r for r in validar(**argumentos) if r.validacao == nome)


def test_ptax_divergente_falha(montagem):
    cambio = montagem.cambio.copy()
    cambio.loc[cambio.index[10], "ptax_media_oficial"] += 0.001
    assert _validacao(montagem, "ptax_media_mensal", cambio=cambio).falhas == 1


def test_excecoes_sao_contadas_exatamente(montagem):
    excecoes = ler_excecoes()
    assert _validacao(montagem, "comparacao_fontes").excecoes_aplicadas == len(excecoes)
    # Uma exceção a menos: a divergência daquele mês volta a ser falha.
    assert _validacao(montagem, "comparacao_fontes", excecoes=excecoes.iloc[1:]).falhas == 1
    # Uma exceção para um mês sem divergência: também falha (exceção que deixou de existir).
    sobra = excecoes.iloc[[0]].assign(mes="2010-01")
    resultado = _validacao(montagem, "comparacao_fontes", excecoes=pd.concat([excecoes, sobra]))
    assert resultado.falhas == 1


def test_mes_faltando_falha(montagem):
    precos = montagem.precos
    meio = precos[(precos.serie == "cafe_arabica_bm") & (precos.mes == "2015-03")].index
    assert _validacao(montagem, "continuidade", precos=precos.drop(meio)).falhas == 1
    # Antes do mês-base a série não é usada: lacuna ali não conta.
    antes = precos[(precos.serie == "cafe_arabica_bm") & (precos.mes == "1985-03")].index
    assert _validacao(montagem, "continuidade", precos=precos.drop(antes)).falhas == 0


def test_variacao_do_fmi_confere_com_a_oficial(montagem):
    resultado = _validacao(montagem, "variacao_fmi")
    assert resultado.verificados > 800 and resultado.maior_diferenca < 1e-9


# --------------------------------------------------------------------------- indicadores


def test_preco_em_reais_e_a_conversao_declarada(montagem):
    linhas = montagem.mensal[montagem.mensal.lado == "internacional"]
    esperado = linhas.preco_usd_kg * linhas.ptax_media * KG_POR_SACA
    assert np.allclose(linhas.preco_brl_saca, esperado, atol=1e-4)
    fmi = linhas[linhas.fonte == "fmi_pcps"]
    assert np.allclose(fmi.preco_usd_kg, fmi.valor_original / 100 / 0.45359237, atol=1e-6)


def test_indice_volta_as_variacoes(montagem):
    for serie, bruto in montagem.mensal.groupby("serie"):
        grupo = bruto.sort_values("mes")
        composto = 100 * (1 + grupo.variacao_mensal / 100).cumprod()
        # No IPCA o índice do mart encadeia as variações oficiais; nos preços, idem por construção.
        assert np.allclose(grupo.indice_base_100, composto, rtol=2e-4), serie


def test_acumulado_12m_e_a_razao_dos_indices(montagem):
    for serie, bruto in montagem.mensal.groupby("serie"):
        grupo = bruto.sort_values("mes").set_index("mes")
        indice = grupo.indice_base_100
        razao = (indice / indice.shift(12) - 1) * 100
        comum = razao.dropna().index
        assert np.allclose(grupo.variacao_acum_12m[comum], razao[comum], atol=1e-5), serie


def test_preco_real_e_razao_sao_identidades(montagem):
    mensal = montagem.mensal
    geral = mensal[mensal.serie == CAFE.deflator.id].set_index("mes").indice_base_100
    moido = mensal[mensal.serie == CAFE.id_principal].set_index("mes").indice_base_100
    precos = mensal[(mensal.lado == "internacional") & mensal.mes.isin(geral.index)]
    real = precos.preco_brl_saca * geral.iloc[-1] / precos.mes.map(geral)
    assert np.allclose(precos.preco_real_brl_saca, real, atol=1e-4)
    razao = precos.mes.map(moido) / precos.indice_base_100 * 100
    assert np.allclose(precos.razao_consumidor_preco, razao, atol=1e-4)
    # Depois do último mês do IPCA não há deflator nem razão.
    depois = mensal[(mensal.lado == "internacional") & ~mensal.mes.isin(geral.index)]
    assert depois.preco_real_brl_saca.isna().all() and depois.razao_consumidor_preco.isna().all()


def test_ipca_e_repetido_sem_alteracao(montagem):
    assert conferir(CAFE, montagem) == []
    ipca = pd.read_csv(RAIZ / "data" / "marts" / "ipca_mensal.csv", dtype={"chave_categoria": str})
    moido = montagem.mensal[montagem.mensal.serie == CAFE.id_principal]
    juntas = moido.merge(ipca, on=["mes", "chave_categoria"], suffixes=("", "_ipca"))
    assert len(juntas) == len(moido) == 243
    assert (juntas.variacao_mensal == juntas.variacao_mensal_ipca).all()
    assert (juntas.indice_base_100 == juntas.indice_base_100_ipca).all()


def test_defasagens(montagem):
    defasagens = montagem.defasagens
    assert defasagens.correlacao.between(-1, 1).all()
    assert len(defasagens) == len(CAFE.internacionais) * 2 * (CAFE.defasagem_maxima + 1)
    # Reproduz uma correlação à mão: arábica (FMI) em t-3 contra o café moído em t.
    mensal = montagem.mensal
    x = mensal[mensal.serie == "cafe_arabica_fmi"].set_index("mes").variacao_mensal
    y = mensal[mensal.serie == CAFE.id_principal].set_index("mes").variacao_mensal
    x.index = [(pd.Period(m, "M") + 3).strftime("%Y-%m") for m in x.index]
    par = pd.concat([x, y], axis=1, join="inner").dropna()
    linha = defasagens[
        (defasagens.serie == "cafe_arabica_fmi")
        & (defasagens.medida == "variacao_mensal")
        & (defasagens.defasagem_meses == 3)
    ].iloc[0]
    assert linha.correlacao == pytest.approx(par.iloc[:, 0].corr(par.iloc[:, 1]), abs=1e-6)
    assert linha.observacoes == len(par)


def test_mes_sem_cambio_nao_vira_preco_em_reais(montagem):
    cambio = montagem.cambio[montagem.cambio.mes != "2015-03"]
    mensal = calcular_mensal(CAFE, cambio, montagem.precos, montagem.consumidor)
    assert not ((mensal.mes == "2015-03") & (mensal.lado == "internacional")).any()


# --------------------------------------------------------------------------- publicação


@pytest.fixture(scope="module")
def publicado(tmp_path_factory):
    destino = tmp_path_factory.mktemp("cafe")
    (destino / "data").mkdir()
    shutil.copy(RAIZ / "data" / "metadata.json", destino / "data" / "metadata.json")
    assert publicar(destino) == []
    return destino


def test_publicacao_reproduz_o_repositorio(publicado):
    # Strings exatas; números com tolerância de 1e-6 (diferença entre CPUs, A-031).
    for nome in ["cafe_mensal.csv", "cafe_defasagens.csv"]:
        esperado = pd.read_csv(RAIZ / "data" / "marts" / nome, dtype=str, keep_default_na=False)
        obtido = pd.read_csv(publicado / "data" / "marts" / nome, dtype=str, keep_default_na=False)
        assert list(esperado.columns) == list(obtido.columns), nome
        assert len(esperado) == len(obtido), nome
        for coluna in esperado.columns:
            if esperado[coluna].equals(obtido[coluna]):
                continue
            a = pd.to_numeric(esperado[coluna].replace("", np.nan))
            b = pd.to_numeric(obtido[coluna].replace("", np.nan))
            assert np.allclose(a, b, atol=1e-6, equal_nan=True), f"{nome}: {coluna}"
    readme = "cafe_README.md"
    assert (RAIZ / "data" / "marts" / readme).read_text() == (
        publicado / "data" / "marts" / readme
    ).read_text()


def test_metadados_do_cafe_conferem(publicado):
    documento = json.loads((RAIZ / "data" / "metadata.json").read_text())["cafe"]
    for nome, descricao in documento["arquivos"].items():
        conteudo = (RAIZ / "data" / "marts" / nome).read_bytes()
        assert hashlib.sha256(conteudo).hexdigest() == descricao["sha256"], nome
        assert descricao["linhas"] == conteudo.count(b"\n") - 1, nome
    obtido = json.loads((publicado / "data" / "metadata.json").read_text())
    assert {k: v for k, v in obtido.items() if k != "cafe"} == {
        k: v
        for k, v in json.loads((RAIZ / "data" / "metadata.json").read_text()).items()
        if k != "cafe"
    }, "publicar o café não pode mexer nos metadados dos índices"
    assert all(v["ok"] for v in documento["validacoes"])


def test_dicionario_documenta_todas_as_colunas(publicado):
    readme = (publicado / "data" / "marts" / "cafe_README.md").read_text()
    for nome, especificacao in DICIONARIO.items():
        assert f"cafe_{nome}.csv" in readme
        for coluna in especificacao["colunas"]:
            assert f"`{coluna}`" in readme


def test_publicacao_bloqueada_nao_grava(tmp_path, monkeypatch):
    original = modulo.montar

    def com_falha(configuracao, produto):
        montagem = original(configuracao, produto)
        montagem.resultados[0] = replace(montagem.resultados[0], falhas=1)
        return montagem

    monkeypatch.setattr(modulo, "montar", com_falha)
    assert publicar(tmp_path) == ["validação ptax_media_mensal falhou"]
    assert list(tmp_path.rglob("*")) == []


def test_workflow_do_cafe_roda_depois_dos_indices_e_testa_antes_do_commit():
    workflow = yaml.safe_load((RAIZ / ".github/workflows/atualizacao.yml").read_text())
    cafe = workflow["jobs"]["cafe"]
    assert cafe["needs"] == "atualizar"  # o mart do café lê o mart do IPCA já atualizado
    passos = [p.get("name", "") for p in cafe["steps"]]
    assert passos.index("Testes do café") < passos.index("Commit e push na main")
    assert "cafe" in workflow[True]["workflow_dispatch"]["inputs"]["indice"]["options"]
