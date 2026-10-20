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
from macroaf.extract.ibge_metadados import (
    Periodicidade,
    baixar_metadados,
    numero_categorias,
    periodicidade,
)
from macroaf.extract.raw import ArmazemRaw
from macroaf.extract.sidra import baixar_mes

JANELA_REVISAO = 3


class AguardandoDivulgacao(RuntimeError):
    """A tabela de dados está um mês atrás da referência: o IBGE ainda está publicando.

    No dia da divulgação, a 3065 e a tabela de dados podem ser atualizadas em horários diferentes
    (decisão 0003, item 6). Não é troca de tabela; a execução seguinte completa.
    """


class CatalogoDivergente(RuntimeError):
    """O catálogo não bate com os metadados da fonte."""


def meses_entre(inicio: str, fim: str) -> list[str]:
    """Todos os meses de `inicio` a `fim`, inclusive, no formato AAAA-MM."""
    primeiro, ultimo = periodo_em_meses(inicio), periodo_em_meses(fim)
    return [f"{m // 12:04d}-{m % 12 + 1:02d}" for m in range(primeiro, ultimo + 1)]


def divergencias(
    tabela: Tabela, publicada: Periodicidade, ultimo_salvo: str | None = None
) -> list[str]:
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
    if ultimo_salvo is not None and periodo_em_meses(publicada.fim) < periodo_em_meses(
        ultimo_salvo
    ):
        problemas.append(
            f"tabela {tabela.tabela}: metadados vão até {publicada.fim}, "
            f"mas o raw já tem {ultimo_salvo}"
        )
    return problemas


def defasagem_maxima(publicadas: dict[int, Periodicidade], indice: Indice) -> int:
    """Quantos meses a tabela de dados aberta mais atrasada está atrás da referência."""
    abertas = [t for t in indice.tabelas if t.fim is None and t.tabela in publicadas]
    referencias = [publicadas[t.tabela].fim for t in abertas if t.papel == "referencia"]
    if not referencias:
        return 0
    fim = periodo_em_meses(max(referencias))
    return max(
        (fim - periodo_em_meses(publicadas[t.tabela].fim) for t in abertas if t.papel == "dados"),
        default=0,
    )


def tabelas_paradas(publicadas: dict[int, Periodicidade], indice: Indice) -> list[str]:
    """Tabela de dados aberta que ficou para trás da referência: sinal de troca de tabela (#27)."""
    abertas = [t for t in indice.tabelas if t.fim is None and t.tabela in publicadas]
    referencias = [t for t in abertas if t.papel == "referencia"]
    if not referencias:
        return []
    fim_referencia = max(publicadas[t.tabela].fim for t in referencias)
    return [
        f"tabela {t.tabela}: publicada até {publicadas[t.tabela].fim}, mas a referência "
        f"já vai até {fim_referencia} (troca de tabela? ver #27)"
        for t in abertas
        if t.papel == "dados" and publicadas[t.tabela].fim != fim_referencia
    ]


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
    metadados: list[int] = field(default_factory=list)
    ultimo_publicado: dict[int, str] = field(default_factory=dict)

    @property
    def total_novos(self) -> int:
        return sum(len(p) for p in self.novos.values())

    @property
    def total_revisados(self) -> int:
        return sum(len(p) for p in self.revisados.values())

    @property
    def houve_mudanca(self) -> bool:
        """Algo novo no raw: mês, revisão de mês ou metadados."""
        return bool(self.total_novos or self.total_revisados or self.metadados)


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
    publicadas = {}
    metadados = {}
    for tabela in selecionadas:
        url, conteudo, lidos = baixar_metadados(cliente, fonte, tabela.tabela)
        metadados[tabela.tabela] = (url, conteudo, lidos)
        publicada = publicadas[tabela.tabela] = periodicidade(lidos)
        salvos = armazem.periodos(tabela.tabela)
        problemas += divergencias(tabela, publicada, salvos[-1] if salvos else None)
        planos.append(planejar(tabela, publicada, salvos, janela_revisao, ate))
    paradas = tabelas_paradas(publicadas, indice)
    if paradas and not problemas and defasagem_maxima(publicadas, indice) == 1:
        raise AguardandoDivulgacao("; ".join(paradas))
    problemas += paradas
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
        url, conteudo, lidos = metadados[numero]
        if armazem.salvar_metadados(numero, url, conteudo) is not None:
            log(f"{indice.codigo} {numero}: metadados novos ou alterados gravados")
            relatorio.metadados.append(numero)
        esperados = len(plano.tabela.variaveis) * numero_categorias(
            lidos, plano.tabela.classificacao
        )
        for periodo in plano.novos:
            url, conteudo = baixar_mes(cliente, fonte, plano.tabela, periodo, esperados)
            armazem.salvar(numero, periodo, url, conteudo)
            relatorio.novos.setdefault(numero, []).append(periodo)
        for periodo in plano.revisao:
            url, conteudo = baixar_mes(cliente, fonte, plano.tabela, periodo, esperados)
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


def extrair(
    codigo_indice: str,
    *,
    verificar: bool = False,
    tabelas: set[int] | None = None,
    ate: str | None = None,
    janela_revisao: int = JANELA_REVISAO,
) -> tuple[int, Relatorio | None]:
    """Atualiza o raw de um índice.

    Códigos: 0 = ok; 1 = erro da fonte ou do raw; 2 = catálogo diverge dos metadados (provável
    troca de tabela, #27); 3 = aguardando o IBGE terminar a divulgação do mês (nada gravado).
    """
    catalogo = carregar_catalogo()
    indice = catalogo.indices[codigo_indice]
    armazem = ArmazemRaw(indice.fonte)
    try:
        with Cliente() as cliente:
            relatorio = atualizar_indice(
                catalogo,
                indice,
                cliente,
                armazem,
                verificar=verificar,
                tabelas=tabelas,
                ate=ate,
                janela_revisao=janela_revisao,
            )
    except AguardandoDivulgacao as erro:
        print(f"aguardando a divulgação completar: {erro}")
        return 3, None
    except CatalogoDivergente as erro:
        print(f"catálogo divergente dos metadados: {erro}", file=sys.stderr)
        return 2, None
    except (ErroFonte, httpx.HTTPError) as erro:
        print(f"erro da fonte: {erro}", file=sys.stderr)
        return 1, None
    except (OSError, EOFError) as erro:
        print(f"erro ao ler ou gravar o raw: {erro}", file=sys.stderr)
        return 1, None
    return 0, relatorio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--indice", default="ipca15", help="código do índice no catálogo")
    parser.add_argument("--tabela", type=int, action="append", help="limita a estas tabelas")
    parser.add_argument("--ate", help="último mês a baixar (AAAA-MM)")
    parser.add_argument("--verificar", action="store_true", help="só confere, sem baixar valores")
    parser.add_argument("--janela-revisao", type=int, default=JANELA_REVISAO)
    args = parser.parse_args(argv)

    catalogo = carregar_catalogo()
    if args.indice not in catalogo.indices:
        parser.error(f"índice desconhecido: {args.indice} (catálogo: {sorted(catalogo.indices)})")
    codigo, relatorio = extrair(
        args.indice,
        verificar=args.verificar,
        tabelas=set(args.tabela) if args.tabela else None,
        ate=args.ate,
        janela_revisao=args.janela_revisao,
    )
    if relatorio is None:
        return 0 if codigo == 3 else codigo
    acao = "a baixar" if args.verificar else "baixados"
    print(f"{relatorio.total_novos} mês(es) {acao}; {relatorio.total_revisados} revisado(s)")
    _escrever_saida_github(relatorio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
