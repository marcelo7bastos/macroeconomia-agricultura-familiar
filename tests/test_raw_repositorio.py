"""Integridade da camada raw versionada: todo arquivo tem manifesto e o conteúdo confere."""

import gzip
import hashlib
import json

import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.extract.raw import DIRETORIO_RAW, METADADOS, ArmazemRaw

FONTES = sorted({i.fonte for i in carregar_catalogo().indices.values()})


@pytest.mark.parametrize("fonte", FONTES)
def test_raw_confere_com_o_manifesto(fonte):
    armazem = ArmazemRaw(fonte)
    manifesto = {linha["arquivo"]: linha for linha in armazem.ler_manifesto()}
    arquivos = sorted(
        p.relative_to(armazem.diretorio).as_posix() for p in armazem.diretorio.glob("*/*.json.gz")
    )
    if not arquivos:
        pytest.skip(f"raw de {fonte} ainda vazio")

    assert sorted(manifesto) == arquivos, "arquivo sem linha no manifesto, ou o contrário"
    for arquivo in arquivos:
        linha = manifesto[arquivo]
        conteudo = gzip.decompress((armazem.diretorio / arquivo).read_bytes())
        assert hashlib.sha256(conteudo).hexdigest() == linha["sha256"], arquivo
        if linha["periodo"] != METADADOS:
            assert len(json.loads(conteudo)) - 1 == int(linha["n_registros"]), arquivo


def test_nao_ha_temporarios_esquecidos():
    assert not list(DIRETORIO_RAW.glob("**/*.tmp"))
