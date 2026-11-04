"""Contratos da explicação: publicação íntegra, oficiais preservados e artefato público."""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from macroaf.catalogo import RAIZ
from macroaf.relatorios import gestao, site


@pytest.fixture(scope="module", params=["ipca", "ipca15"])
def explicacao(request):
    return gestao.coletar(request.param)


def test_explicacao_preserva_geral_e_alimentos_da_publicacao(explicacao):
    dados = explicacao
    codigo = dados["codigo"]
    categorias = pd.read_csv(
        RAIZ / f"data/marts/{codigo}_categorias.csv", dtype={"codigo_ibge": str}
    )
    mensal = pd.read_csv(RAIZ / f"data/marts/{codigo}_mensal.csv")
    ultima = mensal[mensal.mes == dados["fim"]].merge(categorias, on="chave_categoria")
    for codigo_ibge in ["0", "1", "11", "12"]:
        fonte = ultima[ultima.codigo_ibge == codigo_ibge].iloc[0]
        linha = next(
            r
            for r in dados["registros"]
            if r["mes"] == dados["fim"] and r["codigo_ibge"] == codigo_ibge
        )
        assert linha["variacao_mensal"] == fonte.variacao_mensal
        assert linha["peso"] == fonte.peso
    assert max(r["mes"] for r in dados["registros"]) == dados["fim"]
    assert min(r["mes"] for r in dados["registros"]) == dados["inicio"]


def test_html_em_dia_e_sem_dependencias_de_rede(explicacao):
    codigo = explicacao["codigo"]
    html = gestao.gerar(codigo)
    assert html == (RAIZ / f"docs/gestao/{codigo}.html").read_text()
    assert "@@" not in html
    assert "<script src=" not in html
    assert '<link rel="stylesheet"' not in html
    assert 'role="tablist"' in html
    assert "não mede renda do produtor" in html
    assert "não presume que o usuário validou" in html


def test_dados_embutidos_sao_json_valido_com_ausencias_preservadas(explicacao):
    json.dumps(explicacao, allow_nan=False)
    assert all(r["mes"] <= explicacao["fim"] for r in explicacao["registros"])
    assert any(r["acum_12m"] is None for r in explicacao["registros"])


def test_recusa_explicacao_se_csv_nao_corresponde_ao_hash(tmp_path, monkeypatch):
    pasta = tmp_path / "data/marts"
    pasta.mkdir(parents=True)
    meta = json.loads((RAIZ / "data/metadata.json").read_text())
    (tmp_path / "data/metadata.json").write_text(json.dumps(meta))
    primeiro = next(iter(meta["ipca"]["arquivos"]))
    (pasta / primeiro).write_text("conteudo adulterado")
    monkeypatch.setattr(gestao, "RAIZ", tmp_path)
    with pytest.raises(ValueError, match="hash diferente"):
        gestao.coletar("ipca")


def test_site_preserva_dados_e_nao_copia_raw(tmp_path):
    destino = tmp_path / "site"
    site.montar(destino)
    assert (destino / ".nojekyll").exists()
    assert "docs/gestao/ipca.html" in (destino / "index.html").read_text()
    assert not (destino / "data/raw").exists()
    assert not (destino / ".git").exists()
    assert (destino / "docs/transformacoes/ipca15.html").exists()
    assert (destino / "docs/transformacoes/ipca.html").exists()
    for codigo in ["ipca", "ipca15"]:
        arquivo = Path(f"data/marts/{codigo}_mensal.csv")
        assert (
            hashlib.sha256((destino / arquivo).read_bytes()).digest()
            == hashlib.sha256((RAIZ / arquivo).read_bytes()).digest()
        )
    with pytest.raises(ValueError, match="diretório vazio"):
        site.montar(destino)


def test_pagina_do_cafe_em_dia_sem_rede_e_com_os_valores_do_mart():
    html = gestao.gerar_cafe()
    assert html == (RAIZ / "docs/gestao/cafe.html").read_text()
    assert "@@" not in html
    assert "<script src=" not in html
    assert '<link rel="stylesheet"' not in html
    # A explicação vem antes dos números e dos gráficos.
    assert html.index('class="notas"') < html.index('id="numeros"') < html.index('id="g-indice"')
    dados = gestao.coletar_cafe()
    json.dumps(dados, allow_nan=False)
    mensal = pd.read_csv(RAIZ / "data/marts/cafe_mensal.csv")
    for serie in gestao.SERIES_CAFE:
        linhas = mensal[mensal.serie == serie].set_index("mes")
        for i, mes in enumerate(dados["meses"]):
            for campo in gestao.CAMPOS_CAFE:
                esperado = linhas[campo].get(mes)
                obtido = dados["series"][serie][campo][i]
                if esperado is None or pd.isna(esperado):
                    assert obtido is None, (serie, mes, campo)
                else:
                    assert obtido == esperado, (serie, mes, campo)
    defasagens = pd.read_csv(RAIZ / "data/marts/cafe_defasagens.csv")
    for (serie, medida), grupo in defasagens.groupby(["serie", "medida"]):
        esperado = grupo.sort_values("defasagem_meses").correlacao.tolist()
        assert dados["defasagens"][serie][medida] == esperado
    assert (
        dados["fim"]
        == json.loads((RAIZ / "data/metadata.json").read_text())["cafe"]["series"][
            "ipca_cafe_moido"
        ]["fim"]
    )


def test_pagina_do_cafe_recusa_csv_fora_do_hash(tmp_path, monkeypatch):
    pasta = tmp_path / "data/marts"
    pasta.mkdir(parents=True)
    meta = json.loads((RAIZ / "data/metadata.json").read_text())
    (tmp_path / "data/metadata.json").write_text(json.dumps(meta))
    (tmp_path / "reference").mkdir()
    for nome in meta["cafe"]["arquivos"]:
        (pasta / nome).write_text("conteudo adulterado")
    monkeypatch.setattr(gestao, "RAIZ", tmp_path)
    with pytest.raises(ValueError, match="hash diferente"):
        gestao.coletar_cafe()


def test_site_leva_a_pagina_do_cafe(tmp_path):
    destino = tmp_path / "site"
    site.montar(destino)
    assert (destino / "docs/gestao/cafe.html").exists()
    assert (destino / "data/marts/cafe_mensal.csv").exists()
    assert "docs/gestao/cafe.html" in (destino / "index.html").read_text()
