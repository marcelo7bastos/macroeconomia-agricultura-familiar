"""Gráficos em SVG para as páginas geradas: linhas e barras, sem biblioteca externa.

As cores vêm de variáveis CSS da página (`--serie-1`, `--serie-2`, `--positivo`, `--negativo`),
validadas para os temas claro e escuro. Cada gráfico de linha leva `data-rotulos` (um texto por
ponto) para o JS da página desenhar a régua e a dica ao passar o mouse.
"""

from __future__ import annotations

import json
import math
from html import escape

MENOS = "\u2212"  # sinal de menos tipográfico
TRACO = "\u2013"  # valor ausente
LARGURA = 960
MARGEM = {"esquerda": 52, "direita": 16, "topo": 16, "base": 30}


def _passo_eixo(minimo: float, maximo: float, alvo: int = 5) -> float:
    bruto = (maximo - minimo) / alvo or 1.0
    potencia = 10 ** math.floor(math.log10(bruto))
    return next(p * potencia for p in (1, 2, 2.5, 5, 10) if p * potencia >= bruto)


MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _mes(periodo: str) -> str:
    return f"{MESES[int(periodo[5:7]) - 1]}/{periodo[:4]}"


def _num(valor: float, casas: int = 1, enxuto: bool = False) -> str:
    """Número com vírgula decimal; `enxuto` tira decimais zerados (rótulos de eixo)."""
    texto = f"{valor:.{casas}f}".replace(".", ",").replace("-", MENOS)
    if enxuto and casas and texto.endswith("," + "0" * casas):
        texto = texto[: -(casas + 1)]
    return texto


def linha(
    rotulo: str,
    meses: list[str],
    series: list[tuple[str, str, list[float | None]]],
    unidade: str = "%",
    marcas: list[tuple[str, str]] = (),
    altura: int = 260,
    zero: bool = True,
) -> str:
    """Gráfico de linhas. `series`: (nome, classe CSS, valores). `marcas`: (mês, texto) verticais."""
    valores = [v for _, _, vs in series for v in vs if v is not None]
    minimo, maximo = min(valores), max(valores)
    if zero:
        minimo = min(minimo, 0.0)
    passo = _passo_eixo(minimo, maximo)
    minimo = math.floor(minimo / passo) * passo
    maximo = math.ceil(maximo / passo) * passo
    x0, x1 = MARGEM["esquerda"], LARGURA - MARGEM["direita"]
    y0, y1 = altura - MARGEM["base"], MARGEM["topo"]
    dx = (x1 - x0) / max(len(meses) - 1, 1)

    def y(v: float) -> float:
        return y0 - (v - minimo) / (maximo - minimo) * (y0 - y1)

    partes = []
    marca = minimo
    while marca <= maximo + passo / 2:
        classe = "eixo" if abs(marca) < passo / 1000 else "grade"
        partes.append(
            f'<line class="{classe}" x1="{x0}" x2="{x1}" y1="{y(marca):.1f}" y2="{y(marca):.1f}"/>'
        )
        partes.append(
            f'<text class="t3" x="{x0 - 6}" y="{y(marca) + 4:.1f}" text-anchor="end">{_num(marca, 1, enxuto=True)}</text>'
        )
        marca += passo
    anos = sorted({m[:4] for m in meses})
    salto = max(1, len(anos) // 10)
    for ano in anos[::salto]:
        if f"{ano}-01" in meses:
            x = x0 + meses.index(f"{ano}-01") * dx
            partes.append(
                f'<text class="t3" x="{x:.1f}" y="{y0 + 18}" text-anchor="middle">{ano}</text>'
            )
    for mes, texto in marcas:
        if mes in meses:
            x = x0 + meses.index(mes) * dx
            partes.append(f'<line class="troca" x1="{x:.1f}" x2="{x:.1f}" y1="{y1}" y2="{y0}"/>')
            partes.append(
                f'<text class="t3 troca-t" x="{x + 4:.1f}" y="{y1 + 10}">{escape(texto)}</text>'
            )
    for nome, classe, vs in series:
        pontos, trecho = [], []
        for i, v in enumerate(vs):
            if v is None:
                if trecho:
                    pontos.append(trecho)
                trecho = []
                continue
            trecho.append(f"{x0 + i * dx:.1f},{y(v):.1f}")
        if trecho:
            pontos.append(trecho)
        for t in pontos:
            partes.append(
                f'<polyline class="linha {classe}" points="{" ".join(t)}"><title>{escape(nome)}</title></polyline>'
            )
    rotulos = [
        f"{_mes(m)}: "
        + " · ".join(
            f"{nome} {_num(vs[i], 2) if vs[i] is not None else TRACO}{unidade}"
            for nome, _, vs in series
        )
        for i, m in enumerate(meses)
    ]
    return (
        f'<svg class="grafico grafico-linha" viewBox="0 0 {LARGURA} {altura}" role="img" aria-label="{escape(rotulo)}" '
        f'data-x0="{x0}" data-dx="{dx:.4f}" data-y0="{y0}" data-y1="{y1}" data-rotulos="{escape(json.dumps(rotulos, ensure_ascii=False))}">'
        + "".join(partes)
        + f'<line class="regua" x1="0" x2="0" y1="{y1}" y2="{y0}" visibility="hidden"/></svg>'
    )


def barras(
    rotulo: str,
    categorias: list[str],
    valores: list[float],
    unidade: str = "",
    casas: int = 2,
    altura_barra: int = 26,
    largura_rotulo: int = 230,
) -> str:
    """Barras horizontais a partir do zero; positivo e negativo com cores opostas."""
    minimo, maximo = min(0.0, *valores), max(0.0, *valores)
    x0, x1 = largura_rotulo, LARGURA - 70
    escala = (x1 - x0) / ((maximo - minimo) or 1)
    zero = x0 - minimo * escala
    altura = len(categorias) * altura_barra + 8
    partes = [f'<line class="eixo" x1="{zero:.1f}" x2="{zero:.1f}" y1="0" y2="{altura}"/>']
    for i, (nome, v) in enumerate(zip(categorias, valores, strict=True)):
        topo = i * altura_barra + 4
        largura = abs(v) * escala
        x = zero if v >= 0 else zero - largura
        classe = "positivo" if v >= 0 else "negativo"
        texto = f"{_num(v, casas)}{unidade}"
        partes.append(
            f'<g class="barra-g"><title>{escape(nome)}: {texto}</title>'
            f'<rect class="barra-h {classe}" x="{x:.1f}" y="{topo + 4}" width="{max(largura, 1):.1f}" height="{altura_barra - 10}" rx="3"/>'
            f'<text class="t2" x="{x0 - 10}" y="{topo + altura_barra / 2 + 3}" text-anchor="end">{escape(nome)}</text>'
            # Negativo: o valor fica à direita do zero, para não colidir com o nome da categoria.
            f'<text class="t2 valor" x="{(x + largura + 6) if v >= 0 else (zero + 6):.1f}" y="{topo + altura_barra / 2 + 3}">{texto}</text></g>'
        )
    return (
        f'<svg class="grafico" viewBox="0 0 {LARGURA} {altura}" role="img" aria-label="{escape(rotulo)}">'
        + "".join(partes)
        + "</svg>"
    )
