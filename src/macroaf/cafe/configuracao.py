"""Leitura e validação de `config/precos.yaml`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from macroaf.catalogo import RAIZ, ErroCatalogo, periodo_em_meses

CAMINHO_PADRAO = RAIZ / "config" / "precos.yaml"
VERSAO_ESQUEMA = 1
FONTES_CONHECIDAS = {"bcb_sgs", "fmi_pcps", "banco_mundial_cmo"}
UNIDADES = {"US¢/lb", "US$/kg"}


@dataclass(frozen=True)
class SerieInternacional:
    id: str
    nome: str
    fonte: str
    codigo: str
    unidade: str


@dataclass(frozen=True)
class SerieConsumidor:
    id: str
    codigo_ibge: int


@dataclass(frozen=True)
class Produto:
    codigo: str
    nome: str
    inicio: str
    base_indice: str
    internacionais: tuple[SerieInternacional, ...]
    comparacoes: tuple[tuple[str, str], ...]
    limite_comparacao_pct: float
    indice_consumidor: str
    principal: int
    subitens: tuple[SerieConsumidor, ...]
    deflator: SerieConsumidor
    defasagem_maxima: int

    def internacional(self, id_serie: str) -> SerieInternacional:
        return next(s for s in self.internacionais if s.id == id_serie)

    @property
    def id_principal(self) -> str:
        return next(s.id for s in self.subitens if s.codigo_ibge == self.principal)


@dataclass(frozen=True)
class Cambio:
    serie_diaria: int
    serie_media_mensal: int
    inicio: str


@dataclass(frozen=True)
class ConfiguracaoPrecos:
    fontes: dict[str, dict[str, Any]]
    cambio: Cambio
    produtos: dict[str, Produto]


def _exigir(dados: Any, campo: str, contexto: str) -> Any:
    if not isinstance(dados, dict) or dados.get(campo) in (None, ""):
        raise ErroCatalogo(f"{contexto}: campo obrigatório ausente: {campo}")
    return dados[campo]


def carregar(caminho: Path | str = CAMINHO_PADRAO) -> ConfiguracaoPrecos:
    with Path(caminho).open(encoding="utf-8") as arquivo:
        bruto = yaml.safe_load(arquivo)
    if _exigir(bruto, "versao_esquema", "precos") != VERSAO_ESQUEMA:
        raise ErroCatalogo(f"precos: versao_esquema não suportada (esperado {VERSAO_ESQUEMA})")
    fontes = _exigir(bruto, "fontes", "precos")
    desconhecidas = set(fontes) - FONTES_CONHECIDAS
    if desconhecidas:
        raise ErroCatalogo(f"precos: fontes sem leitor: {sorted(desconhecidas)}")
    for codigo, dados in fontes.items():
        for campo in ["nome", "url", "licenca", "ficha"]:
            _exigir(dados, campo, f"fonte {codigo}")
        if not (RAIZ / dados["ficha"]).is_file():
            raise ErroCatalogo(f"fonte {codigo}: ficha inexistente: {dados['ficha']}")

    bruto_cambio = _exigir(bruto, "cambio", "precos")
    cambio = Cambio(
        serie_diaria=int(_exigir(bruto_cambio["diaria"], "serie", "cambio.diaria")),
        serie_media_mensal=int(_exigir(bruto_cambio["media_mensal"], "serie", "cambio.mensal")),
        inicio=str(_exigir(bruto_cambio, "inicio", "cambio")),
    )
    periodo_em_meses(cambio.inicio)

    produtos = {
        codigo: _montar_produto(codigo, dados, fontes, cambio)
        for codigo, dados in _exigir(bruto, "produtos", "precos").items()
    }
    return ConfiguracaoPrecos(fontes=fontes, cambio=cambio, produtos=produtos)


def _montar_produto(codigo: str, dados: Any, fontes: dict, cambio: Cambio) -> Produto:
    contexto = f"produto {codigo}"
    internacionais = tuple(
        SerieInternacional(
            id=_exigir(s, "id", contexto),
            nome=_exigir(s, "nome", contexto),
            fonte=_exigir(s, "fonte", contexto),
            codigo=str(_exigir(s, "codigo", contexto)),
            unidade=_exigir(s, "unidade", contexto),
        )
        for s in _exigir(dados, "internacionais", contexto)
    )
    ids = [s.id for s in internacionais]
    for serie in internacionais:
        if serie.fonte not in fontes:
            raise ErroCatalogo(f"{contexto}: série {serie.id} com fonte desconhecida")
        if serie.unidade not in UNIDADES:
            raise ErroCatalogo(f"{contexto}: série {serie.id} com unidade sem conversão")
    consumidor = _exigir(dados, "consumidor", contexto)
    subitens = tuple(
        SerieConsumidor(id=s["id"], codigo_ibge=int(s["codigo_ibge"]))
        for s in _exigir(consumidor, "subitens", contexto)
    )
    deflator = SerieConsumidor(
        id=consumidor["deflator"]["id"], codigo_ibge=int(consumidor["deflator"]["codigo_ibge"])
    )
    ids += [s.id for s in subitens] + [deflator.id]
    if len(ids) != len(set(ids)):
        raise ErroCatalogo(f"{contexto}: ids de série repetidos")
    comparacoes = tuple(tuple(par) for par in dados.get("comparacoes", []))
    for par in comparacoes:
        if len(par) != 2 or not set(par) <= set(ids):
            raise ErroCatalogo(f"{contexto}: comparação inválida: {par}")
    produto = Produto(
        codigo=codigo,
        nome=_exigir(dados, "nome", contexto),
        inicio=str(_exigir(dados, "inicio", contexto)),
        base_indice=str(_exigir(dados, "base_indice", contexto)),
        internacionais=internacionais,
        comparacoes=comparacoes,
        limite_comparacao_pct=float(_exigir(dados, "limite_comparacao_pct", contexto)),
        indice_consumidor=_exigir(consumidor, "indice", contexto),
        principal=int(_exigir(consumidor, "principal", contexto)),
        subitens=subitens,
        deflator=deflator,
        defasagem_maxima=int(_exigir(dados, "defasagem_maxima", contexto)),
    )
    if periodo_em_meses(produto.base_indice) + 1 != periodo_em_meses(produto.inicio):
        raise ErroCatalogo(f"{contexto}: base_indice deve ser o mês anterior ao início")
    if periodo_em_meses(cambio.inicio) > periodo_em_meses(produto.base_indice):
        raise ErroCatalogo(f"{contexto}: o câmbio precisa começar até o mês-base")
    if produto.principal not in {s.codigo_ibge for s in subitens}:
        raise ErroCatalogo(f"{contexto}: subitem principal fora da lista")
    return produto
