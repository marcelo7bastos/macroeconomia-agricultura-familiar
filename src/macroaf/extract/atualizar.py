"""Extração incremental: confere o catálogo com os metadados e baixa só o que falta.

Uso:

    uv run python -m macroaf.extract.atualizar                 # extrai o que falta
    uv run python -m macroaf.extract.atualizar --verificar     # só confere, sem baixar valores
    uv run python -m macroaf.extract.atualizar --tabela 7062 --ate 2020-12

Para cada tabela do índice:

1. lê `periodicidade` nos metadados e confere com o catálogo (início sempre; fim das tabelas
   fechadas); divergência interrompe a extração antes de baixar qualquer valor;
2. baixa os meses que ainda não estão no raw;
3. nas tabelas abertas (`fim: null`), baixa de novo os últimos meses (janela de revisão) e guarda
   uma revisão se o conteúdo mudou.

Códigos de saída: 0 sucesso, 1 erro da fonte, 2 catálogo divergente dos metadados.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field

import httpx

from macroaf.catalogo import Catalogo, Indice, Tabela, carregar_catalogo, periodo_em_meses
from macroaf.extract.cliente import Cliente, ErroFonte
from macroaf.extract.ibge_metadados import Periodicidade, obter_metadados, periodicidade
from macroaf.extract.raw import ArmazemRaw
from macroaf.extract.sidra import baixar_mes

JANELA_REVISAO = 3


class CatalogoDivergente(RuntimeError):
    """O catálogo não bate com os metadados da fonte."""


def meses_entre(inicio: str, fim: str) -> list[str]:
    """Todos os meses de `inicio` a `fim`, inclusive, no formato AAAA-MM."""
    primeiro, ultimo = periodo_em_meses(inicio), periodo_em_meses(fim)
    return [f"{m // 12:04d}-{m % 12 + 1:02d}" for m in range(primeiro, ultimo + 1)]


def divergencias(tabela: Tabela, publicada: Periodicidade) -> list[str]:
    problemas = []
    if publicada.inicio != tabela.inicio:
        problemas.append(
            f"tabela {tabela.tabela}: início no catálogo {tabela.inicio}, "
            f"nos metadados {publicada.inicio}"
        )
    if tabela.fim is not None and publicada.fim != tabela.fim:
        problemas.append(
            f"tabela {tabela.tabela}: fim no catálogo {tabela.fim}, nos metadados {publicada.fim}"
        )
    return problemas


@dataclass
class Plano:
    tabela: Tabela
    publicada: Periodicidade
    novos: list[str]
    revisao: list[str]


def planejar(
    tabela: Tabela,
    publicada: Periodicidade,
    salvos: list[str],
    janela_revisao: int = JANELA_REVISAO,
    ate: str | None = None,
) -> Plano:
    fim = tabela.fim or publicada.fim
    if ate is not None and periodo_em_meses(ate) < periodo_em_meses(fim):
        fim = ate
    esperados = (
        meses_entre(tabela.inicio, fim)
        if periodo_em_meses(fim) >= periodo_em_meses(tabela.inicio)
        else []
    )
    ja_salvos = set(salvos)
    novos = [p for p in esperados if p not in ja_salvos]
    revisao = []
    if tabela.fim is None and janela_revisao > 0:
        revisao = [p for p in sorted(ja_salvos) if p in set(esperados)][-janela_revisao:]
    return Plano(tabela=tabela, publicada=publicada, novos=novos, revisao=revisao)


@dataclass
class Relatorio:
    novos: dict[int, list[str]] = field(default_factory=dict)
    revisados: dict[int, list[str]] = field(default_factory=dict)
    ultimo_publicado: dict[int, str] = field(default_factory=dict)

    @property
    def total_novos(self) -> int:
        return sum(len(p) for p in self.novos.values())

    @property
    def total_revisados(self) -> int:
        return sum(len(p) for p in self.revisados.values())


def atualizar_indice(
    catalogo: Catalogo,
    indice: Indice,
    cliente: Cliente,
    armazem: ArmazemRaw,
    verificar: bool = False,
    tabelas: set[int] | None = None,
    ate: str | None = None,
    janela_revisao: int = JANELA_REVISAO,
    log=print,
) -> Relatorio:
    fonte = catalogo.fontes[indice.fonte]
    selecionadas = [t for t in indice.tabelas if tabelas is None or t.tabela in tabelas]

    planos = []
    problemas = []
    for tabela in selecionadas:
        publicada = periodicidade(obter_metadados(cliente, fonte, tabela.tabela))
        problemas += divergencias(tabela, publicada)
        planos.append(
            planejar(tabela, publicada, armazem.periodos(tabela.tabela), janela_revisao, ate)
        )
    if problemas:
        raise CatalogoDivergente("; ".join(problemas))

    relatorio = Relatorio()
    for plano in planos:
        numero = plano.tabela.tabela
        relatorio.ultimo_publicado[numero] = plano.publicada.fim
        log(
            f"{indice.codigo} {numero}: publicado até {plano.publicada.fim}; "
            f"{len(plano.novos)} mês(es) a baixar, {len(plano.revisao)} a revisar"
        )
        if verificar:
            relatorio.novos[numero] = plano.novos
            continue
        for periodo in plano.novos:
            url, conteudo = baixar_mes(cliente, fonte, plano.tabela, periodo)
            armazem.salvar(numero, periodo, url, conteudo)
            relatorio.novos.setdefault(numero, []).append(periodo)
        for periodo in plano.revisao:
            url, conteudo = baixar_mes(cliente, fonte, plano.tabela, periodo)
            if armazem.salvar(numero, periodo, url, conteudo) is not None:
                log(f"{indice.codigo} {numero}: {periodo} revisado pela fonte")
                relatorio.revisados.setdefault(numero, []).append(periodo)
    return relatorio


def _escrever_saida_github(relatorio: Relatorio) -> None:
    caminho = os.environ.get("GITHUB_OUTPUT")
    if not caminho:
        return
    with open(caminho, "a", encoding="utf-8") as arquivo:
        arquivo.write(f"novos={relatorio.total_novos}\n")
        arquivo.write(f"revisados={relatorio.total_revisados}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--indice", default="ipca15")
    parser.add_argument("--tabela", type=int, action="append", help="limita a estas tabelas")
    parser.add_argument("--ate", help="último mês a baixar (AAAA-MM)")
    parser.add_argument("--verificar", action="store_true", help="só confere, sem baixar valores")
    parser.add_argument("--janela-revisao", type=int, default=JANELA_REVISAO)
    args = parser.parse_args(argv)

    catalogo = carregar_catalogo()
    indice = catalogo.indices[args.indice]
    armazem = ArmazemRaw(indice.fonte)
    try:
        with Cliente() as cliente:
            relatorio = atualizar_indice(
                catalogo,
                indice,
                cliente,
                armazem,
                verificar=args.verificar,
                tabelas=set(args.tabela) if args.tabela else None,
                ate=args.ate,
                janela_revisao=args.janela_revisao,
            )
    except CatalogoDivergente as erro:
        print(f"catálogo divergente dos metadados: {erro}", file=sys.stderr)
        return 2
    except (ErroFonte, httpx.HTTPError) as erro:
        print(f"erro da fonte: {erro}", file=sys.stderr)
        return 1

    acao = "a baixar" if args.verificar else "baixados"
    print(f"{relatorio.total_novos} mês(es) {acao}; {relatorio.total_revisados} revisado(s)")
    _escrever_saida_github(relatorio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
