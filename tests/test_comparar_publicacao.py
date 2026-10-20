import csv
import hashlib
import json

import pytest
from comparar_publicacao import comparar_csvs, comparar_exatos, comparar_metadados


@pytest.mark.parametrize(
    ("tipo", "coluna", "origem", "valor_a", "valor_b", "aceito"),
    [
        ("acumulados", "acum_12m", "calculado", "10", "10.001", True),
        ("acumulados", "acum_12m", "calculado", "10", "9.999", True),
        ("acumulados", "acum_12m", "calculado", "10", "10.001001", False),
        ("acumulados", "acum_12m", "calculado", "10", "9.998999", False),
        ("acumulados", "acum_12m", "calculado", "1000000", "1000000.002", False),
        ("acumulados", "acum_12m", "oficial", "10", "10.000001", False),
        ("contribuicoes", "contrib_ano", None, "0.000373", "0.001373", True),
        ("contribuicoes", "contrib_ano", None, "0.000373", "-0.000627", True),
        ("contribuicoes", "contrib_ano", None, "0.000373", "0.001374", False),
        ("contribuicoes", "contrib_ano", None, "-0.0", "0.0", True),
        ("mensal", "contribuicao_pp", None, "0", "0.001", True),
        ("mensal", "contribuicao_pp", None, "0", "0.001001", False),
        ("mensal", "variacao_mensal", None, "1.00", "1.000001", False),
        ("mensal", "peso", None, "1.00", "1.000001", False),
        ("mensal", "variacao_acum_ano_publicada", None, "1", "1.000001", False),
        ("mensal", "variacao_acum_12m_publicada", None, "1", "1.000001", False),
        ("mensal", "indice_base_100", None, "100", "100.000001", False),
        ("mensal", "sazonalidade_media", None, "1", "1.000001", False),
        ("contribuicoes", "contrib_ano", None, "", "0", False),
        ("contribuicoes", "contrib_ano", None, "0", "", False),
        ("contribuicoes", "contrib_ano", None, "", "", True),
        ("contribuicoes", "contrib_ano", None, "1", "NaN", False),
        ("contribuicoes", "contrib_ano", None, "1", "Infinity", False),
        ("contribuicoes", "contrib_ano", None, "1", "texto", False),
        ("categorias", "codigo_ibge", None, "001", "1", False),
        ("categorias", "nome", None, "Arroz", "arroz", False),
        ("categorias", "serie_inicio", None, "2020-01", "2020-02", False),
    ],
)
def test_tolerancia_so_nos_calculados_com_limite_absoluto(
    tmp_path, tipo, coluna, origem, valor_a, valor_b, aceito
):
    caminhos = [tmp_path / "esperado" / f"ipca15_{tipo}.csv", tmp_path / f"ipca15_{tipo}.csv"]
    for caminho, valor in zip(caminhos, [valor_a, valor_b], strict=True):
        caminho.parent.mkdir(exist_ok=True)
        cabecalho, linha = [coluna], [valor]
        if origem:
            cabecalho.append("origem_12m")
            linha.append(origem)
        with caminho.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(cabecalho)
            escritor.writerow(linha)
    if aceito:
        comparar_csvs(*caminhos, "ipca15")
    else:
        with pytest.raises(pytest.fail.Exception, match=f"coluna {coluna}"):
            comparar_csvs(*caminhos, "ipca15")


@pytest.mark.parametrize(
    "alterado",
    [
        "mes,chave_categoria,acum_ano,origem_ano\n2020-01,1.1,1,oficial\n",
        "mes,chave_categoria,acum_ano,origem_ano\n2020-01,1.2,1,calculado\n",
        "mes,chave_categoria,acum_ano,origem_ano\n2020-02,1.1,1,calculado\n",
        "mes,chave_categoria,acum_ano,origem_ano\n",
        "mes,chave_categoria,acum_ano,origem_ano\n2020-01,1.1,1,calculado\n2020-02,1.1,1,calculado\n",
        "mes,chave_categoria,acum_ano,origem_ano\n2020-01,1.1,1\n",
        "mes,chave_categoria,acum_ano,origem_ano\n2020-01,1.1,1,calculado,extra\n",
        "chave_categoria,mes,acum_ano,origem_ano\n1.1,2020-01,1,calculado\n",
    ],
)
def test_estrutura_e_origem_continuam_exatas(tmp_path, alterado):
    esperado = tmp_path / "ipca15_acumulados.csv"
    obtido = tmp_path / "obtido.csv"
    esperado.write_text(
        "mes,chave_categoria,acum_ano,origem_ano\n2020-01,1.1,1,calculado\n", encoding="utf-8"
    )
    obtido.write_text(alterado, encoding="utf-8")
    with pytest.raises(pytest.fail.Exception):
        comparar_csvs(esperado, obtido, "ipca15")


def test_diferenca_grande_tem_mensagem_curta():
    with pytest.raises(pytest.fail.Exception) as erro:
        comparar_exatos(b"a" * 1_000_000, b"b" * 1_000_000, "arquivo.csv")
    assert len(str(erro.value)) < 150
    assert "arquivo.csv" in str(erro.value)


@pytest.mark.parametrize("defeito", [None, "hash_esperado", "hash_obtido", "linhas", "coleta"])
def test_hashes_conferem_com_os_proprios_arquivos_e_demais_metadados_sao_exatos(tmp_path, defeito):
    caminhos = []
    for nome, valor in [("esperado", "1.0000"), ("obtido", "1.0001")]:
        pasta = tmp_path / nome / "data"
        (pasta / "marts").mkdir(parents=True)
        conteudo = f"acum_ano,origem_ano\n{valor},calculado\n".encode()
        (pasta / "marts/ipca15_acumulados.csv").write_bytes(conteudo)
        resumo = {"linhas": 1, "colunas": ["acum_ano", "origem_ano"]}
        resumo["sha256"] = hashlib.sha256(conteudo).hexdigest()
        documento = {
            "ipca15": {"arquivos": {"ipca15_acumulados.csv": resumo}, "coleta": "2026-10-20"}
        }
        if defeito == f"hash_{nome}":
            resumo["sha256"] = "0" * 64
        if nome == "obtido" and defeito == "linhas":
            resumo["linhas"] = 2
        if nome == "obtido" and defeito == "coleta":
            documento["ipca15"]["coleta"] = "2026-10-19"
        caminho = pasta / "metadata.json"
        caminho.write_text(json.dumps(documento), encoding="utf-8")
        caminhos.append(caminho)
    if defeito:
        with pytest.raises(pytest.fail.Exception):
            comparar_metadados(*caminhos, "ipca15")
    else:
        comparar_csvs(
            caminhos[0].parent / "marts/ipca15_acumulados.csv",
            caminhos[1].parent / "marts/ipca15_acumulados.csv",
            "ipca15",
        )
        comparar_metadados(*caminhos, "ipca15")
