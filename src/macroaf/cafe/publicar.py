"""Confere e publica os marts do piloto do café.

    uv run python -m macroaf.cafe.publicar

Saídas (nomes estáveis, lidos pelo Power BI pelas URLs do raw do GitHub):

- `data/marts/cafe_mensal.csv` e `data/marts/cafe_defasagens.csv`;
- `data/marts/cafe_README.md`, dicionário gerado;
- chave `cafe` em `data/metadata.json`: último mês de cada série, coleta, validações e hashes.

Com qualquer validação ou conferência falhando, nada é gravado.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from macroaf.cafe.configuracao import ConfiguracaoPrecos, Produto, carregar
from macroaf.cafe.montar import COLUNAS_DEFASAGENS, COLUNAS_MENSAL, Montagem, montar
from macroaf.catalogo import RAIZ
from macroaf.extract.raw_arquivos import ArmazemArquivos

FONTES_RAW = ["bcb_sgs", "fmi_pcps", "banco_mundial_cmo"]

DICIONARIO = {
    "mensal": {
        "chave": ["mes", "serie"],
        "colunas": {
            "mes": "Mês de referência, AAAA-MM.",
            "serie": "Identificador estável da série (ver tabela de séries).",
            "nome": "Nome da série.",
            "lado": "`internacional` (preço de mercado) ou `consumidor` (IPCA).",
            "fonte": "`fmi_pcps`, `banco_mundial_cmo` ou `ipca`.",
            "chave_categoria": "Só no IPCA: chave da categoria em `ipca_categorias.csv` (tabela.codigo SIDRA).",
            "unidade_original": "Unidade publicada pela fonte (`US¢/lb` no FMI, `US$/kg` no Banco Mundial).",
            "valor_original": "Preço como publicado pela fonte, na unidade original. Oficial.",
            "ptax_media": "Média mensal da PTAX venda (R$/US$), calculada dos dias úteis da série SGS 1; validada contra a média oficial (SGS 3698). Calculado.",
            "preco_usd_kg": "Preço em US$/kg (FMI: US¢/lb ÷ 100 ÷ 0,45359237). Calculado.",
            "preco_brl_saca": "Preço em R$ por saca de 60 kg: `preco_usd_kg × ptax_media × 60`. Calculado.",
            "variacao_mensal": "Variação mensal, %. No IPCA, a oficial; nos preços, a do `preco_brl_saca` (calculada).",
            "variacao_acum_12m": "Variação acumulada em 12 meses, %. Calculada pelo número-índice (no IPCA, validada contra a variável oficial onde ela existe).",
            "indice_base_100": "Número-índice com base no mês anterior ao início (jun/2006 = 100). No IPCA, o do mart `ipca_mensal.csv`; nos preços, `preco_brl_saca` ÷ preço do mês-base × 100 (calculado).",
            "preco_real_brl_saca": "`preco_brl_saca` a preços do último mês do IPCA, deflacionado pelo índice geral. Vazio depois do último mês do IPCA. Calculado.",
            "razao_consumidor_preco": "Índice do café moído (IPCA) ÷ índice do preço internacional × 100. Acima de 100: o consumidor acumulou mais alta que o preço internacional em reais desde jun/2006. Leitura de direção, não de margem. Calculado.",
        },
    },
    "defasagens": {
        "chave": ["serie", "medida", "defasagem_meses"],
        "colunas": {
            "serie": "Série de preço internacional.",
            "medida": "`variacao_mensal` ou `variacao_acum_12m` (as duas em R$).",
            "defasagem_meses": "k: o preço no mês t-k comparado com o café moído no mês t.",
            "correlacao": "Correlação de Pearson entre as duas medidas. Descritiva, sem leitura causal; no acumulado em 12 meses as janelas se sobrepõem e a correlação fica inflada. Calculado.",
            "observacoes": "Número de pares de meses usados.",
            "inicio": "Primeiro mês t do intervalo comum.",
            "fim": "Último mês t do intervalo comum.",
        },
    },
}


def _csv(tabela: pd.DataFrame) -> bytes:
    texto = io.StringIO()
    tabela.to_csv(texto, index=False, lineterminator="\n")
    return texto.getvalue().encode("utf-8")


def conferir(produto: Produto, montagem: Montagem) -> list[str]:
    """Contratos do mart que não são validações das fontes: chaves, colunas e o IPCA intacto."""
    problemas = []
    mensal, defasagens = montagem.mensal, montagem.defasagens
    if list(mensal.columns) != COLUNAS_MENSAL or list(defasagens.columns) != COLUNAS_DEFASAGENS:
        problemas.append("colunas fora do dicionário")
    for nome, tabela in [("mensal", mensal), ("defasagens", defasagens)]:
        if tabela.duplicated(DICIONARIO[nome]["chave"]).any():
            problemas.append(f"{nome}: chave repetida")
        numericas = tabela.select_dtypes("number")
        if np.isinf(numericas).any().any():
            problemas.append(f"{nome}: valor infinito")
    ipca = mensal[mensal.lado == "consumidor"].merge(
        montagem.consumidor, on=["mes", "serie"], suffixes=("", "_mart")
    )
    for coluna in ["variacao_mensal", "indice_base_100", "chave_categoria"]:
        obtido, esperado = ipca[coluna], ipca[f"{coluna}_mart"]
        if coluna == "chave_categoria":
            obtido, esperado = obtido.astype(str), esperado.astype(str)
        if not obtido.equals(esperado):
            problemas.append(f"IPCA: {coluna} difere do mart do IPCA")
    if len(ipca) != len(montagem.consumidor[montagem.consumidor.mes >= produto.inicio]):
        problemas.append("IPCA: linhas perdidas ou a mais")
    if not defasagens.correlacao.between(-1, 1).all():
        problemas.append("defasagens: correlação fora de [-1, 1]")
    return problemas


def _readme(configuracao: ConfiguracaoPrecos, produto: Produto, montagem: Montagem) -> str:
    mensal = montagem.mensal
    linhas = [
        "# Dicionário dos marts do café",
        "",
        "Gerado por `uv run python -m macroaf.cafe.publicar`; não edite à mão. Projeto: "
        "[piloto do café](../../docs/projetos/cafe-piloto.md) (#62).",
        "",
        "Preços internacionais do café (FMI e Banco Mundial) convertidos para R$ por saca de 60 kg "
        "pela PTAX média do mês (Banco Central), ao lado dos subitens de café do IPCA. Os valores "
        "do IPCA são os do mart `ipca_mensal.csv`, sem recálculo.",
        "",
        "## Séries",
        "",
        "| `serie` | Nome | Fonte | Unidade original | Primeiro mês | Último mês |",
        "|---|---|---|---|---|---|",
    ]
    for serie, grupo in mensal.groupby("serie", sort=False):
        primeira = grupo.iloc[0]
        unidade = primeira.unidade_original if isinstance(primeira.unidade_original, str) else "—"
        linhas.append(
            f"| `{serie}` | {primeira.nome} | `{primeira.fonte}` | {unidade} | "
            f"{grupo.mes.min()} | {grupo.mes.max()} |"
        )
    for nome, especificacao in DICIONARIO.items():
        linhas += [
            "",
            f"## `cafe_{nome}.csv`",
            "",
            f"Chave: {', '.join(f'`{c}`' for c in especificacao['chave'])}.",
            "",
            "| Coluna | Descrição |",
            "|---|---|",
        ]
        linhas += [f"| `{c}` | {d} |" for c, d in especificacao["colunas"].items()]
    linhas += [
        "",
        "## Fontes e licenças",
        "",
    ]
    linhas += [
        f"- **{dados['nome']}** — {dados['licenca']}. Ficha: `{dados['ficha']}`."
        for dados in configuracao.fontes.values()
    ]
    linhas += [
        "- **IBGE, IPCA** — via marts do projeto (CC BY 4.0, `LICENSE-DADOS.md`).",
        "",
        "## Cuidados de leitura",
        "",
        "- Café moído é produto industrializado (torra, embalagem, marca) e mistura tipos; os "
        "preços internacionais são de café verde exportado. As razões mostram direção e "
        "defasagem, não margem.",
        "- O IBGE não publica a composição do café moído entre arábica e robusta; as séries ficam "
        "separadas e nenhuma cesta é inventada.",
        "- A conversão usa a PTAX média do mês sobre o preço médio do mês: aproximação do preço "
        "diário convertido pelo câmbio do dia, que as fontes não publicam.",
        "- FMI e Banco Mundial publicam a mesma família de cotações da OIC; diferenças acima de "
        "1% estão registradas em `reference/excecoes_validacao_cafe.csv`, sem ajuste.",
        "- Possível fonte futura: indicadores CEPEA/Esalq de arábica e robusta (mercado físico "
        "brasileiro), se o CEPEA autorizar acesso automatizado (ver o projeto).",
        "",
    ]
    return "\n".join(linhas)


def publicar(destino: Path = RAIZ, produto_codigo: str = "cafe") -> list[str]:
    configuracao = carregar()
    produto = configuracao.produtos[produto_codigo]
    montagem = montar(configuracao, produto)
    problemas = [f"validação {r.validacao} falhou" for r in montagem.resultados if not r.ok]
    problemas += conferir(produto, montagem)
    if problemas:
        return problemas

    pasta = destino / "data" / "marts"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivos = {}
    for nome, tabela in [("mensal", montagem.mensal), ("defasagens", montagem.defasagens)]:
        conteudo = _csv(tabela)
        (pasta / f"{produto.codigo}_{nome}.csv").write_bytes(conteudo)
        arquivos[f"{produto.codigo}_{nome}.csv"] = {
            "linhas": len(tabela),
            "colunas": list(tabela.columns),
            "sha256": hashlib.sha256(conteudo).hexdigest(),
        }
    (pasta / f"{produto.codigo}_README.md").write_text(
        _readme(configuracao, produto, montagem), encoding="utf-8"
    )

    coletas = [
        linha["data_coleta"]
        for fonte in FONTES_RAW
        for linha in ArmazemArquivos(fonte).ler_manifesto()
    ]
    metadados = {
        "produto": produto.codigo,
        "nome": produto.nome,
        "ultima_coleta": max(coletas),
        "series": {
            serie: {"inicio": g.mes.min(), "fim": g.mes.max()}
            for serie, g in montagem.mensal.groupby("serie")
        },
        "validacoes": [
            {k: v for k, v in asdict(r).items() if k != "exemplos"} | {"ok": r.ok}
            for r in montagem.resultados
        ],
        "arquivos": arquivos,
    }
    caminho_meta = destino / "data" / "metadata.json"
    existente = json.loads(caminho_meta.read_text()) if caminho_meta.exists() else {}
    existente[produto.codigo] = metadados
    caminho_meta.write_text(
        json.dumps(existente, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Confere e publica os marts do café.")
    parser.parse_args(argv)
    problemas = publicar()
    if problemas:
        print("Publicação bloqueada:", file=sys.stderr)
        for problema in problemas:
            print(f"  - {problema}", file=sys.stderr)
        return 1
    print("Marts do café publicados em data/marts/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
