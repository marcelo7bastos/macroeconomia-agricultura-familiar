"""Camada raw das fontes de preços: respostas guardadas como vieram, compactadas, com manifesto.

Mesmos princípios da camada raw do SIDRA (`extract/raw.py`, decisão 0003), com chaves livres:

    data/raw/<fonte>/<serie>/<chave>.<ext>.gz        primeira coleta
    data/raw/<fonte>/<serie>/<chave>.r2.<ext>.gz     revisão (conteúdo mudou numa coleta posterior)
    data/raw/<fonte>/manifesto.csv                   uma linha por arquivo salvo

`chave` é o período coberto pelo arquivo (`AAAAMM`) ou `completo`, para fontes que devolvem a
série inteira a cada consulta. Uma revisão só é gravada se o conteúdo canônico mudou: o canônico
ignora o que muda a cada consulta sem mudar os dados (como a hora de preparo da resposta).
Nada é sobrescrito nem apagado; gravação atômica; SHA-256 sobre os bytes guardados (descompactados).
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import os
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from macroaf.extract.raw import DIRETORIO_RAW

CAMPOS_MANIFESTO = [
    "serie",
    "chave",
    "revisao",
    "arquivo",
    "url",
    "data_coleta",
    "sha256",
    "n_registros",
    "bytes",
    "observacao",
]
_PADRAO_ARQUIVO = re.compile(r"^(\d{6}|completo)(?:\.r(\d+))?\.(json|xml|csv)\.gz$")


@dataclass(frozen=True)
class EntradaManifesto:
    serie: str
    chave: str
    revisao: int
    arquivo: str  # relativo ao diretório da fonte
    url: str
    data_coleta: str
    sha256: str
    n_registros: int
    bytes: int
    observacao: str = ""


class ArmazemArquivos:
    """Lê e grava a camada raw de uma fonte de preços."""

    def __init__(self, fonte: str, raiz: Path = DIRETORIO_RAW) -> None:
        self.diretorio = raiz / fonte
        self.manifesto = self.diretorio / "manifesto.csv"

    def revisoes(self, serie: str) -> dict[str, list[tuple[int, Path]]]:
        """Arquivos salvos por chave, em ordem de revisão (1 = primeira coleta)."""
        resultado: dict[str, list[tuple[int, Path]]] = {}
        pasta = self.diretorio / serie
        if not pasta.is_dir():
            return resultado
        for arquivo in pasta.iterdir():
            correspondencia = _PADRAO_ARQUIVO.match(arquivo.name)
            if correspondencia:
                chave, revisao, _ = correspondencia.groups()
                resultado.setdefault(chave, []).append((int(revisao or 1), arquivo))
        for lista in resultado.values():
            lista.sort()
        return resultado

    def chaves(self, serie: str) -> list[str]:
        return sorted(self.revisoes(serie))

    def vigente(self, serie: str, chave: str) -> Path | None:
        lista = self.revisoes(serie).get(chave)
        return lista[-1][1] if lista else None

    def vigentes(self, serie: str) -> dict[str, Path]:
        return {chave: lista[-1][1] for chave, lista in sorted(self.revisoes(serie).items())}

    @staticmethod
    def ler(arquivo: Path) -> bytes:
        return gzip.decompress(arquivo.read_bytes())

    def salvar(
        self,
        serie: str,
        chave: str,
        extensao: str,
        url: str,
        conteudo: bytes,
        canonico: Callable[[bytes], object],
        n_registros: int,
        observacao: str = "",
    ) -> EntradaManifesto | None:
        """Grava o conteúdo se é novo ou mudou (pelo canônico); `None` se nada mudou."""
        lista = self.revisoes(serie).get(chave, [])
        if lista and canonico(self.ler(lista[-1][1])) == canonico(conteudo):
            return None

        revisao = lista[-1][0] + 1 if lista else 1
        nome = f"{chave}.{extensao}.gz" if revisao == 1 else f"{chave}.r{revisao}.{extensao}.gz"
        pasta = self.diretorio / serie
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / nome
        if destino.exists():
            raise FileExistsError(f"{destino} já existe e a camada raw não sobrescreve")
        temporario = destino.with_name(destino.name + ".tmp")
        temporario.write_bytes(gzip.compress(conteudo, mtime=0))
        os.replace(temporario, destino)

        entrada = EntradaManifesto(
            serie=serie,
            chave=chave,
            revisao=revisao,
            arquivo=destino.relative_to(self.diretorio).as_posix(),
            url=url,
            data_coleta=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            sha256=hashlib.sha256(conteudo).hexdigest(),
            n_registros=n_registros,
            bytes=len(conteudo),
            observacao=observacao,
        )
        self._registrar(entrada)
        return entrada

    def _registrar(self, entrada: EntradaManifesto) -> None:
        novo = not self.manifesto.exists()
        self.diretorio.mkdir(parents=True, exist_ok=True)
        with self.manifesto.open("a", newline="", encoding="utf-8") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS_MANIFESTO, lineterminator="\n")
            if novo:
                escritor.writeheader()
            escritor.writerow(asdict(entrada))

    def ler_manifesto(self) -> list[dict[str, str]]:
        if not self.manifesto.exists():
            return []
        with self.manifesto.open(encoding="utf-8", newline="") as arquivo:
            return list(csv.DictReader(arquivo))
