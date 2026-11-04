"""Leitores das fontes de preços: o que cada fonte devolve e como vira linhas.

Cada leitor separa duas coisas: a coleta (URL, bytes exatos, gravação no raw) e a leitura dos
bytes guardados (`ler_*`), que é a única usada pela transformação. Nenhum valor é convertido aqui.
"""

from __future__ import annotations

import calendar
import csv
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

import openpyxl

from macroaf.cafe.configuracao import ConfiguracaoPrecos, SerieInternacional
from macroaf.extract.cliente import Cliente, ErroFonte
from macroaf.extract.raw_arquivos import ArmazemArquivos, EntradaManifesto

COMPLETO = "completo"


class ErroFormato(ErroFonte):
    """A resposta guardada não tem o formato que o leitor conhece: falha sem adivinhar."""


# --------------------------------------------------------------------------- BCB / SGS


def url_sgs(modelo: str, serie: int, ano: int, mes: int) -> str:
    ultimo = calendar.monthrange(ano, mes)[1]
    return (
        modelo.format(serie=serie)
        + f"?formato=json&dataInicial=01/{mes:02d}/{ano}&dataFinal={ultimo:02d}/{mes:02d}/{ano}"
    )


def ler_sgs(conteudo: bytes) -> list[tuple[date, float]]:
    """Linhas `(data, valor)` de uma resposta do SGS; valor como publicado."""
    try:
        dados = json.loads(conteudo)
    except json.JSONDecodeError as erro:
        raise ErroFormato(f"SGS: resposta não é JSON: {erro}") from None
    if not isinstance(dados, list):
        raise ErroFormato(f"SGS: esperado uma lista, veio {type(dados).__name__}")
    linhas = []
    for item in dados:
        if set(item) != {"data", "valor"}:
            raise ErroFormato(f"SGS: campos inesperados: {sorted(item)}")
        dia, mes, ano = (int(p) for p in item["data"].split("/"))
        linhas.append((date(ano, mes, dia), float(item["valor"])))
    return linhas


def _meses(inicio: str, fim: date) -> Iterator[tuple[int, int]]:
    """Meses completos de `inicio` (AAAA-MM) até o mês anterior a `fim`."""
    ano, mes = (int(p) for p in inicio.split("-"))
    while (ano, mes) < (fim.year, fim.month):
        yield ano, mes
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def coletar_sgs(
    configuracao: ConfiguracaoPrecos,
    cliente: Cliente,
    hoje: date,
    raiz=None,
    verificar: bool = False,
) -> list[EntradaManifesto | str]:
    """Baixa os meses completos que faltam das séries de câmbio, um arquivo por mês.

    Meses passados do SGS não são revistos pelo BCB; por isso só se pede o que não está no raw.
    O mês corrente fica de fora até terminar (a média mensal oficial só sai depois).
    """
    fonte = configuracao.fontes["bcb_sgs"]
    armazem = ArmazemArquivos("bcb_sgs", **({"raiz": raiz} if raiz else {}))
    resultado: list[EntradaManifesto | str] = []
    cambio = configuracao.cambio
    for serie in [cambio.serie_diaria, cambio.serie_media_mensal]:
        existentes = set(armazem.chaves(str(serie)))
        for ano, mes in _meses(cambio.inicio, hoje):
            chave = f"{ano}{mes:02d}"
            if chave in existentes:
                continue
            url = url_sgs(fonte["url"], serie, ano, mes)
            if verificar:
                resultado.append(f"sgs {serie} {ano}-{mes:02d}")
                continue
            conteudo = cliente.obter(url)
            linhas = ler_sgs(conteudo)
            if not linhas:
                raise ErroFormato(f"SGS {serie}: mês {ano}-{mes:02d} sem valores")
            entrada = armazem.salvar(str(serie), chave, "json", url, conteudo, ler_sgs, len(linhas))
            if entrada:
                resultado.append(entrada)
    return resultado


# --------------------------------------------------------------------------- FMI / PCPS

TRANSFORMACOES_FMI = ("USD", "INDEX_PCH")


def chave_fmi(series: list[SerieInternacional]) -> str:
    codigos = "+".join(s.codigo for s in series)
    return f"G001.{codigos}.{'+'.join(TRANSFORMACOES_FMI)}.M"


@dataclass(frozen=True)
class ObservacaoFmi:
    indicador: str
    transformacao: str
    mes: str  # AAAA-MM
    valor: float


def ler_fmi(conteudo: bytes) -> list[ObservacaoFmi]:
    """Observações de uma resposta SDMX 2.1 (structure specific) do PCPS."""
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError as erro:
        raise ErroFormato(f"FMI: XML inválido: {erro}") from None
    observacoes = []
    for serie in raiz.iter():
        if not serie.tag.endswith("Series"):
            continue
        if serie.get("COUNTRY") != "G001" or serie.get("FREQUENCY") != "M":
            raise ErroFormato(f"FMI: série inesperada: {dict(serie.attrib)}")
        if serie.get("SCALE") not in (None, "0"):
            raise ErroFormato(f"FMI: escala inesperada: {serie.get('SCALE')}")
        for obs in serie:
            periodo = obs.get("TIME_PERIOD", "")
            correspondencia = re.fullmatch(r"(\d{4})-M(\d{2})", periodo)
            if not correspondencia or obs.get("OBS_VALUE") in (None, ""):
                raise ErroFormato(f"FMI: observação inesperada: {dict(obs.attrib)}")
            observacoes.append(
                ObservacaoFmi(
                    indicador=serie.get("INDICATOR"),
                    transformacao=serie.get("DATA_TRANSFORMATION"),
                    mes=f"{correspondencia.group(1)}-{correspondencia.group(2)}",
                    valor=float(obs.get("OBS_VALUE")),
                )
            )
    if not observacoes:
        raise ErroFormato("FMI: resposta sem observações")
    return sorted(observacoes, key=lambda o: (o.indicador, o.transformacao, o.mes))


def coletar_fmi(
    configuracao: ConfiguracaoPrecos, cliente: Cliente, raiz=None, verificar: bool = False
) -> list[EntradaManifesto | str]:
    """Baixa a série inteira (preço em US$ e variação mensal oficial); grava se mudou."""
    resultado: list[EntradaManifesto | str] = []
    armazem = ArmazemArquivos("fmi_pcps", **({"raiz": raiz} if raiz else {}))
    for produto in configuracao.produtos.values():
        series = [s for s in produto.internacionais if s.fonte == "fmi_pcps"]
        if not series:
            continue
        url = configuracao.fontes["fmi_pcps"]["url"].format(chave=chave_fmi(series))
        conteudo = cliente.obter(url)
        observacoes = ler_fmi(conteudo)
        faltam = {s.codigo for s in series} - {o.indicador for o in observacoes}
        if faltam:
            raise ErroFormato(f"FMI: indicadores ausentes na resposta: {sorted(faltam)}")
        if verificar:
            atual = armazem.vigente(produto.codigo, COMPLETO)
            if atual is None or ler_fmi(armazem.ler(atual)) != observacoes:
                resultado.append(f"fmi {produto.codigo}: série nova ou revista")
            continue
        entrada = armazem.salvar(
            produto.codigo, COMPLETO, "xml", url, conteudo, ler_fmi, len(observacoes)
        )
        if entrada:
            resultado.append(entrada)
    return resultado


# --------------------------------------------------------------------------- Banco Mundial

_PADRAO_PERIODO_BM = re.compile(r"^(\d{4})M(\d{2})$")
CAMPOS_BM = ["mes", "codigo", "unidade", "valor"]


def link_banco_mundial(pagina: bytes, arquivo: str) -> str:
    """Link da planilha mensal na página do Pink Sheet; o endereço muda a cada edição."""
    links = sorted(
        set(re.findall(rb'href="(https://[^"]+/' + re.escape(arquivo.encode()) + rb')"', pagina))
    )
    if len(links) != 1:
        raise ErroFormato(f"Banco Mundial: esperado um link para {arquivo}, achei {len(links)}")
    return links[0].decode()


def recortar_banco_mundial(planilha: bytes, aba: str, codigos: list[str]) -> tuple[bytes, str]:
    """CSV com as colunas pedidas da aba mensal, valores como estão na planilha.

    Devolve também a linha "Updated on ..." da planilha, que vai para o manifesto.
    """
    try:
        livro = openpyxl.load_workbook(io.BytesIO(planilha), read_only=True, data_only=True)
    except Exception as erro:  # o openpyxl levanta vários tipos para arquivo corrompido
        raise ErroFormato(f"Banco Mundial: planilha ilegível: {erro}") from None
    if aba not in livro.sheetnames:
        raise ErroFormato(f"Banco Mundial: aba {aba!r} ausente ({livro.sheetnames})")
    linhas = list(livro[aba].iter_rows(values_only=True))
    atualizacao = next(
        (str(lin[0]) for lin in linhas[:10] if lin and str(lin[0] or "").startswith("Updated on")),
        "",
    )
    cabecalho = next(
        (i for i, lin in enumerate(linhas[:20]) if all(c in lin for c in codigos)), None
    )
    if cabecalho is None:
        raise ErroFormato(f"Banco Mundial: colunas {codigos} não encontradas no cabeçalho")
    nomes, unidades = linhas[cabecalho], linhas[cabecalho + 1]
    texto = io.StringIO()
    escritor = csv.writer(texto, lineterminator="\n")
    escritor.writerow(CAMPOS_BM)
    for linha in linhas[cabecalho + 2 :]:
        if linha[0] is None:
            continue
        correspondencia = _PADRAO_PERIODO_BM.match(str(linha[0]))
        if not correspondencia:
            raise ErroFormato(f"Banco Mundial: período inesperado: {linha[0]!r}")
        mes = f"{correspondencia.group(1)}-{correspondencia.group(2)}"
        for codigo in codigos:
            coluna = nomes.index(codigo)
            valor = linha[coluna]
            if isinstance(valor, int | float):
                escritor.writerow(
                    [mes, codigo, str(unidades[coluna]).strip("()"), repr(float(valor))]
                )
            elif valor not in (None, "", "…", "..."):
                raise ErroFormato(f"Banco Mundial: valor não numérico em {mes} {codigo}: {valor!r}")
    return texto.getvalue().encode("utf-8"), atualizacao


def ler_banco_mundial(conteudo: bytes) -> list[dict[str, str]]:
    linhas = list(csv.DictReader(io.StringIO(conteudo.decode("utf-8"))))
    if not linhas or list(linhas[0]) != CAMPOS_BM:
        raise ErroFormato("Banco Mundial: recorte sem as colunas esperadas")
    return linhas


def coletar_banco_mundial(
    configuracao: ConfiguracaoPrecos, cliente: Cliente, raiz=None, verificar: bool = False
) -> list[EntradaManifesto | str]:
    """Acha a planilha da edição corrente, recorta as colunas do produto e grava se mudou.

    O raw guarda o recorte (e não a planilha de ~600 kB inteira, que mudaria todo mês); o
    manifesto registra a URL da planilha e o SHA-256 dela, para auditoria.
    """
    fonte = configuracao.fontes["banco_mundial_cmo"]
    resultado: list[EntradaManifesto | str] = []
    armazem = ArmazemArquivos("banco_mundial_cmo", **({"raiz": raiz} if raiz else {}))
    url = link_banco_mundial(cliente.obter(fonte["url"]), fonte["arquivo"])
    planilha = cliente.obter(url)
    for produto in configuracao.produtos.values():
        codigos = [s.codigo for s in produto.internacionais if s.fonte == "banco_mundial_cmo"]
        if not codigos:
            continue
        recorte, atualizacao = recortar_banco_mundial(planilha, fonte["aba"], codigos)
        if verificar:
            atual = armazem.vigente(produto.codigo, COMPLETO)
            if atual is None or armazem.ler(atual) != recorte:
                resultado.append(f"banco mundial {produto.codigo}: série nova ou revista")
            continue
        observacao = (
            f"recorte das colunas {codigos} da aba {fonte['aba']}; planilha sha256 "
            f"{hashlib.sha256(planilha).hexdigest()}; {atualizacao}"
        )
        entrada = armazem.salvar(
            produto.codigo,
            COMPLETO,
            "csv",
            url,
            recorte,
            lambda b: b,
            len(ler_banco_mundial(recorte)),
            observacao,
        )
        if entrada:
            resultado.append(entrada)
    return resultado
