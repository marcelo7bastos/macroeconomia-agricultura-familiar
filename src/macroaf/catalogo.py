"""Leitura e validação do catálogo de séries (`config/series.yaml`)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_PADRAO = RAIZ / "config" / "series.yaml"

VERSAO_ESQUEMA = 1
PAPEIS = {"dados", "referencia"}
# Só o que a sucessão de tabelas sabe validar; outras frequências entram com a issue que as usar.
FREQUENCIAS = {"mensal"}
_PADRAO_PERIODO = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


class ErroCatalogo(ValueError):
    """O catálogo não segue o esquema esperado."""


@dataclass(frozen=True)
class Fonte:
    codigo: str
    nome: str
    api_valores: str
    ficha: str
    api_metadados: str | None = None


@dataclass(frozen=True)
class Variavel:
    codigo: int
    nome: str
    descricao: str
    unidade: str


@dataclass(frozen=True)
class Tabela:
    tabela: int
    papel: str
    inicio: str
    fim: str | None
    variaveis: tuple[int, ...]
    versao_pof: str | None
    classificacao: int | None


@dataclass(frozen=True)
class Indice:
    codigo: str
    nome: str
    descricao: str
    fonte: str
    frequencia: str
    ficha: str
    classificacao: int | None
    variaveis: dict[int, Variavel]
    tabelas: tuple[Tabela, ...]

    @property
    def tabelas_dados(self) -> tuple[Tabela, ...]:
        return tuple(t for t in self.tabelas if t.papel == "dados")

    @property
    def tabelas_referencia(self) -> tuple[Tabela, ...]:
        return tuple(t for t in self.tabelas if t.papel == "referencia")


@dataclass(frozen=True)
class Catalogo:
    versao_esquema: int
    fontes: dict[str, Fonte]
    indices: dict[str, Indice]


def periodo_em_meses(periodo: str) -> int:
    """Converte `AAAA-MM` num número de meses, para comparar e somar períodos."""
    correspondencia = _PADRAO_PERIODO.match(periodo)
    if not correspondencia:
        raise ErroCatalogo(f"período inválido: {periodo!r} (esperado AAAA-MM)")
    ano, mes = correspondencia.groups()
    return int(ano) * 12 + int(mes) - 1


def carregar_catalogo(caminho: Path | str = CAMINHO_PADRAO) -> Catalogo:
    """Lê o catálogo e valida o esquema; levanta `ErroCatalogo` na primeira inconsistência."""
    with Path(caminho).open(encoding="utf-8") as arquivo:
        bruto = yaml.safe_load(arquivo)
    return _montar_catalogo(bruto)


def _exigir(dados: Any, campo: str, contexto: str, tipo: type | None = None) -> Any:
    if not isinstance(dados, dict):
        raise ErroCatalogo(f"{contexto}: esperado um mapeamento")
    if campo not in dados or dados[campo] in (None, ""):
        raise ErroCatalogo(f"{contexto}: campo obrigatório ausente: {campo}")
    valor = dados[campo]
    if tipo is not None and not isinstance(valor, tipo):
        raise ErroCatalogo(f"{contexto}: {campo} deve ser {tipo.__name__}")
    return valor


def _inteiro(valor: Any, contexto: str) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ErroCatalogo(f"{contexto}: código não numérico: {valor!r}") from None


def _montar_catalogo(bruto: Any) -> Catalogo:
    if not isinstance(bruto, dict):
        raise ErroCatalogo("o catálogo deve ser um mapeamento YAML")
    versao = _exigir(bruto, "versao_esquema", "catálogo")
    if versao != VERSAO_ESQUEMA:
        raise ErroCatalogo(f"versao_esquema {versao} não suportada (esperado {VERSAO_ESQUEMA})")

    fontes = {
        codigo: Fonte(
            codigo=codigo,
            nome=_exigir(dados, "nome", f"fonte {codigo}"),
            api_valores=_exigir(dados, "api_valores", f"fonte {codigo}"),
            ficha=_exigir(dados, "ficha", f"fonte {codigo}"),
            api_metadados=dados.get("api_metadados"),
        )
        for codigo, dados in _exigir(bruto, "fontes", "catálogo", dict).items()
    }
    indices = {
        codigo: _montar_indice(codigo, dados, fontes)
        for codigo, dados in _exigir(bruto, "indices", "catálogo", dict).items()
    }
    return Catalogo(versao_esquema=versao, fontes=fontes, indices=indices)


def _montar_indice(codigo: str, dados: Any, fontes: dict[str, Fonte]) -> Indice:
    contexto = f"índice {codigo}"
    if not isinstance(dados, dict):
        raise ErroCatalogo(f"{contexto}: esperado um mapeamento")
    fonte = _exigir(dados, "fonte", contexto)
    if fonte not in fontes:
        raise ErroCatalogo(f"{contexto}: fonte desconhecida: {fonte}")
    frequencia = _exigir(dados, "frequencia", contexto)
    if frequencia not in FREQUENCIAS:
        raise ErroCatalogo(f"{contexto}: frequência inválida: {frequencia}")

    variaveis = {
        _inteiro(cod, contexto): Variavel(
            codigo=_inteiro(cod, contexto),
            nome=_exigir(var, "nome", f"{contexto}, variável {cod}"),
            descricao=_exigir(var, "descricao", f"{contexto}, variável {cod}"),
            unidade=_exigir(var, "unidade", f"{contexto}, variável {cod}"),
        )
        for cod, var in _exigir(dados, "variaveis", contexto, dict).items()
    }
    nomes = [v.nome for v in variaveis.values()]
    if len(nomes) != len(set(nomes)):
        raise ErroCatalogo(f"{contexto}: nomes de variável repetidos")

    classificacao_indice = dados.get("classificacao")
    tabelas = tuple(
        _montar_tabela(t, contexto, variaveis, classificacao_indice)
        for t in _exigir(dados, "tabelas", contexto, list)
    )
    codigos = [t.tabela for t in tabelas]
    if len(codigos) != len(set(codigos)):
        raise ErroCatalogo(f"{contexto}: tabela repetida")

    indice = Indice(
        codigo=codigo,
        nome=_exigir(dados, "nome", contexto),
        descricao=_exigir(dados, "descricao", contexto),
        fonte=fonte,
        frequencia=frequencia,
        ficha=_exigir(dados, "ficha", contexto),
        classificacao=classificacao_indice,
        variaveis=variaveis,
        tabelas=tabelas,
    )
    _validar_sucessao(indice)
    return indice


def _montar_tabela(
    dados: Any,
    contexto_indice: str,
    variaveis: dict[int, Variavel],
    classificacao_indice: int | None,
) -> Tabela:
    numero = _inteiro(_exigir(dados, "tabela", contexto_indice), contexto_indice)
    contexto = f"{contexto_indice}, tabela {numero}"
    papel = _exigir(dados, "papel", contexto)
    if papel not in PAPEIS:
        raise ErroCatalogo(f"{contexto}: papel inválido: {papel}")

    inicio = str(_exigir(dados, "inicio", contexto))
    fim = dados.get("fim")
    fim = None if fim is None else str(fim)
    if fim is not None and periodo_em_meses(fim) < periodo_em_meses(inicio):
        raise ErroCatalogo(f"{contexto}: fim anterior ao início")
    if fim is None:
        periodo_em_meses(inicio)

    codigos = tuple(_inteiro(v, contexto) for v in _exigir(dados, "variaveis", contexto, list))
    desconhecidas = sorted(set(codigos) - set(variaveis))
    if desconhecidas:
        raise ErroCatalogo(f"{contexto}: variáveis não descritas no índice: {desconhecidas}")

    versao_pof = dados.get("versao_pof")
    return Tabela(
        tabela=numero,
        papel=papel,
        inicio=inicio,
        fim=fim,
        variaveis=codigos,
        versao_pof=None if versao_pof is None else str(versao_pof),
        classificacao=dados.get("classificacao", classificacao_indice),
    )


def _validar_sucessao(indice: Indice) -> None:
    """As tabelas de dados se sucedem mês a mês e só a última fica em aberto (`fim: null`).

    Toda tabela de referência cobre o período inteiro das tabelas de dados.
    """
    contexto = f"índice {indice.codigo}"
    dados = sorted(indice.tabelas_dados, key=lambda t: periodo_em_meses(t.inicio))
    if not dados:
        raise ErroCatalogo(f"{contexto}: nenhuma tabela de dados")

    for anterior, seguinte in pairwise(dados):
        if anterior.fim is None:
            raise ErroCatalogo(f"{contexto}: tabela {anterior.tabela} em aberto antes de outra")
        diferenca = periodo_em_meses(seguinte.inicio) - periodo_em_meses(anterior.fim)
        if diferenca != 1:
            tipo = "lacuna" if diferenca > 1 else "sobreposição"
            raise ErroCatalogo(
                f"{contexto}: {tipo} entre as tabelas "
                f"{anterior.tabela} ({anterior.fim}) e {seguinte.tabela} ({seguinte.inicio})"
            )

    inicio_dados = periodo_em_meses(dados[0].inicio)
    fim_dados = dados[-1].fim
    for referencia in indice.tabelas_referencia:
        nao_cobre_inicio = periodo_em_meses(referencia.inicio) > inicio_dados
        nao_cobre_fim = referencia.fim is not None and (
            fim_dados is None or periodo_em_meses(referencia.fim) < periodo_em_meses(fim_dados)
        )
        if nao_cobre_inicio or nao_cobre_fim:
            raise ErroCatalogo(
                f"{contexto}: referência {referencia.tabela} não cobre o período dos dados"
            )

    versoes = [t.versao_pof for t in dados if t.versao_pof is not None]
    if len(versoes) != len(set(versoes)):
        raise ErroCatalogo(f"{contexto}: versão de POF repetida entre tabelas de dados")
