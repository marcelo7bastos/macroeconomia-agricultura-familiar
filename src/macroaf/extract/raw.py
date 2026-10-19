"""Camada raw: respostas da API guardadas como vieram, compactadas, com manifesto.

Organização (decisão 0003):

    data/raw/<fonte>/<tabela>/<AAAAMM>.json.gz        primeira coleta do mês
    data/raw/<fonte>/<tabela>/<AAAAMM>.r2.json.gz     revisão (conteúdo mudou numa coleta posterior)
    data/raw/<fonte>/manifesto.csv                    uma linha por arquivo salvo

Nada é sobrescrito nem apagado. O SHA-256 é calculado sobre os bytes originais (descompactados).
A compactação usa `mtime=0`, então o mesmo conteúdo gera sempre o mesmo arquivo.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from macroaf.catalogo import RAIZ

DIRETORIO_RAW = RAIZ / "data" / "raw"
_PADRAO_ARQUIVO = re.compile(r"^(\d{6})(?:\.r(\d+))?\.json\.gz$")
CAMPOS_MANIFESTO = [
    "tabela",
    "periodo",
    "revisao",
    "arquivo",
    "url",
    "data_coleta",
    "sha256",
    "n_registros",
    "bytes",
]


@dataclass(frozen=True)
class EntradaManifesto:
    tabela: int
    periodo: str  # AAAA-MM
    revisao: int
    arquivo: str  # relativo ao diretório da fonte
    url: str
    data_coleta: str
    sha256: str
    n_registros: int
    bytes: int


def _conteudo_canonico(conteudo: bytes) -> list:
    """Registros ordenados, para comparar coletas sem depender da ordem devolvida pela API."""
    dados = json.loads(conteudo)
    cabecalho, linhas = dados[0], dados[1:]
    return [cabecalho, sorted(linhas, key=lambda linha: json.dumps(linha, sort_keys=True))]


class ArmazemRaw:
    """Lê e grava a camada raw de uma fonte."""

    def __init__(self, fonte: str, raiz: Path = DIRETORIO_RAW) -> None:
        self.diretorio = raiz / fonte
        self.manifesto = self.diretorio / "manifesto.csv"

    def _diretorio_tabela(self, tabela: int) -> Path:
        return self.diretorio / str(tabela)

    def revisoes(self, tabela: int) -> dict[str, list[tuple[int, Path]]]:
        """Arquivos salvos por período, em ordem de revisão (1 = primeira coleta)."""
        resultado: dict[str, list[tuple[int, Path]]] = {}
        pasta = self._diretorio_tabela(tabela)
        if not pasta.is_dir():
            return resultado
        for arquivo in pasta.iterdir():
            correspondencia = _PADRAO_ARQUIVO.match(arquivo.name)
            if not correspondencia:
                continue
            bruto, revisao = correspondencia.groups()
            periodo = f"{bruto[:4]}-{bruto[4:]}"
            resultado.setdefault(periodo, []).append((int(revisao or 1), arquivo))
        for lista in resultado.values():
            lista.sort()
        return resultado

    def periodos(self, tabela: int) -> list[str]:
        return sorted(self.revisoes(tabela))

    def vigente(self, tabela: int, periodo: str) -> Path | None:
        """Arquivo mais recente de um período (o que a compilação deve usar)."""
        lista = self.revisoes(tabela).get(periodo)
        return lista[-1][1] if lista else None

    @staticmethod
    def ler(arquivo: Path) -> bytes:
        return gzip.decompress(arquivo.read_bytes())

    def salvar(
        self, tabela: int, periodo: str, url: str, conteudo: bytes
    ) -> EntradaManifesto | None:
        """Grava a coleta se o período é novo ou o conteúdo mudou; `None` se nada mudou."""
        atual = self.vigente(tabela, periodo)
        if atual is not None:
            anterior = _conteudo_canonico(self.ler(atual))
            if anterior == _conteudo_canonico(conteudo):
                return None

        revisao = 1 if atual is None else len(self.revisoes(tabela)[periodo]) + 1
        bruto = periodo.replace("-", "")
        nome = f"{bruto}.json.gz" if revisao == 1 else f"{bruto}.r{revisao}.json.gz"
        pasta = self._diretorio_tabela(tabela)
        pasta.mkdir(parents=True, exist_ok=True)
        compactado = gzip.compress(conteudo, compresslevel=9, mtime=0)
        (pasta / nome).write_bytes(compactado)

        entrada = EntradaManifesto(
            tabela=tabela,
            periodo=periodo,
            revisao=revisao,
            arquivo=f"{tabela}/{nome}",
            url=url,
            data_coleta=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            sha256=hashlib.sha256(conteudo).hexdigest(),
            n_registros=len(json.loads(conteudo)) - 1,
            bytes=len(conteudo),
        )
        self._registrar(entrada)
        return entrada

    def _registrar(self, entrada: EntradaManifesto) -> None:
        novo = not self.manifesto.exists()
        self.diretorio.mkdir(parents=True, exist_ok=True)
        with self.manifesto.open("a", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS_MANIFESTO, lineterminator="\n")
            if novo:
                escritor.writeheader()
            escritor.writerow(asdict(entrada))

    def ler_manifesto(self) -> list[dict[str, str]]:
        if not self.manifesto.exists():
            return []
        with self.manifesto.open(encoding="utf-8", newline="") as arquivo:
            return list(csv.DictReader(arquivo))
