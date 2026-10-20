"""Compara publicações sem pedir ao pytest um diff de arquivos de vários megabytes."""

import csv
import hashlib
import json
from decimal import Decimal, InvalidOperation
from itertools import zip_longest
from pathlib import Path

import pytest

from macroaf.marts.publicar import JANELAS_MART

TOLERANCIA_PP = Decimal("0.001")


def comparar_exatos(esperado, obtido, contexto):
    """Falha com uma mensagem curta, inclusive para arquivos ou metadados grandes."""
    if esperado != obtido:
        pytest.fail(f"{contexto}: valores diferentes (comparação exata)", pytrace=False)


def _calculado(tipo, coluna, cabecalho, esperada, obtida):
    if tipo == "contribuicoes":
        return coluna in {f"contrib_{janela}" for janela in JANELAS_MART}
    if tipo == "mensal":
        return coluna == "contribuicao_pp"
    if tipo == "acumulados" and coluna in {f"acum_{janela}" for janela in JANELAS_MART}:
        origem = cabecalho.index(coluna.replace("acum_", "origem_", 1))
        return esperada[origem] == obtida[origem] == "calculado"
    return False


def comparar_csvs(esperado: Path, obtido: Path, indice: str):
    """Tolera até 0,001 p.p. só nos acumulados e contribuições calculados (A-031)."""
    tipo = esperado.stem.removeprefix(f"{indice}_")
    with (
        esperado.open(encoding="utf-8", newline="") as arquivo_a,
        obtido.open(encoding="utf-8", newline="") as arquivo_b,
    ):
        linhas_a, linhas_b = csv.reader(arquivo_a), csv.reader(arquivo_b)
        cabecalho = next(linhas_a)
        comparar_exatos(cabecalho, next(linhas_b), f"{esperado.name}: cabeçalho")
        for numero, (linha_a, linha_b) in enumerate(zip_longest(linhas_a, linhas_b), start=2):
            contexto = f"{esperado.name}: linha {numero}"
            if linha_a is None or linha_b is None:
                pytest.fail(f"{contexto}: quantidade de linhas diferente", pytrace=False)
            comparar_exatos(len(cabecalho), len(linha_a), f"{contexto}: colunas esperadas")
            comparar_exatos(len(cabecalho), len(linha_b), f"{contexto}: colunas obtidas")
            if linha_a == linha_b:
                continue
            for coluna, valor_a, valor_b in zip(cabecalho, linha_a, linha_b, strict=True):
                if valor_a == valor_b:
                    continue
                tolerado = False
                if valor_a and valor_b and _calculado(tipo, coluna, cabecalho, linha_a, linha_b):
                    try:
                        numero_a, numero_b = Decimal(valor_a), Decimal(valor_b)
                        tolerado = (
                            numero_a.is_finite()
                            and numero_b.is_finite()
                            and abs(numero_a - numero_b) <= TOLERANCIA_PP
                        )
                    except InvalidOperation:
                        pass
                if not tolerado:
                    pytest.fail(
                        f"{contexto}, coluna {coluna}: "
                        f"esperado {valor_a[:80]!r}, obtido {valor_b[:80]!r}",
                        pytrace=False,
                    )


def comparar_metadados(esperado: Path, obtido: Path, indice: str):
    """Cada hash confere com seu próprio CSV; os demais metadados continuam exatos."""
    documentos = []
    for caminho in [esperado, obtido]:
        documento = json.loads(caminho.read_text(encoding="utf-8"))
        for nome, descricao in documento[indice]["arquivos"].items():
            with (caminho.parent / "marts" / nome).open("rb") as arquivo:
                calculado = hashlib.file_digest(arquivo, "sha256").hexdigest()
            comparar_exatos(descricao.pop("sha256"), calculado, f"{caminho}: hash de {nome}")
        documentos.append(documento)
    comparar_exatos(*documentos, "metadata.json: metadados sem os hashes verificados")
