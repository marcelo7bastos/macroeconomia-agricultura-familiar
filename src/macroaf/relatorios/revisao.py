"""Página de revisão das propostas de harmonização, com decisões gravadas no banco da página.

As propostas vêm do mapa (`reference/map_harmonizacao_<indice>.csv`) e ficam no próprio HTML; as
decisões (aceita ou rejeitada, com observação) são gravadas pela página no banco do artefato
(coleção `decisoes`, um documento por ligação). Claude lê as decisões e as aplica com
`python -m macroaf.transform.harmonizacao --decisoes <arquivo> --revisor <nome>`.

Uso:

    uv run python -m macroaf.relatorios.revisao     # grava docs/revisao/harmonizacao_ipca15.html
"""

from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path

import pandas as pd

from macroaf.catalogo import RAIZ, Indice, carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.relatorios.transformacoes import CSS
from macroaf.transform.classificacao import montar_dim_classificacao
from macroaf.transform.harmonizacao import id_ligacao, ler_mapa

EXPLICACAO_TIPO = {
    "renomeado": "a mesma categoria com outro nome: aceitar emenda a série",
    "fundido": "várias categorias viraram uma: aceitar confirma a fusão (a série continua no item e quebra no subitem)",
    "dividido": "uma categoria virou várias: aceitar confirma a divisão (a série continua no item e quebra no subitem)",
}


def caminho_pagina(indice: Indice) -> Path:
    return RAIZ / "docs" / "revisao" / f"harmonizacao_{indice.codigo}.html"


def _grupos(mapa: pd.DataFrame) -> list[list[int]]:
    """Propostas ligadas por uma categoria em comum formam um grupo (revisado junto)."""
    propostas = mapa[mapa.situacao == "proposto"]
    pai = {i: i for i in propostas.index}

    def raiz(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    por_categoria = {}
    for i, r in propostas.iterrows():
        for lado in ["origem", "destino"]:
            chave = (lado, r[f"tabela_{lado}"], r[f"codigo_sidra_{lado}"])
            if chave in por_categoria:
                pai[raiz(i)] = raiz(por_categoria[chave])
            else:
                por_categoria[chave] = i
    grupos = {}
    for i in propostas.index:
        grupos.setdefault(raiz(i), []).append(i)
    return list(grupos.values())


def coletar(indice: Indice) -> dict:
    mapa = ler_mapa(indice)
    dim = montar_dim_classificacao(indice, ArmazemRaw(indice.fonte))
    nomes = {(r.tabela_sidra, r.codigo_ibge): r.nome for r in dim.itertuples()}
    pofs = {t.tabela: t.versao_pof for t in indice.tabelas_dados}

    def lado(r, qual: str) -> dict | None:
        if pd.isna(r[f"codigo_sidra_{qual}"]):
            return None
        peso = r["peso_origem_fim" if qual == "origem" else "peso_destino_inicio"]
        return {
            "codigo": r[f"codigo_ibge_{qual}"],
            "nome": r[f"nome_{qual}"],
            "id": int(r[f"codigo_sidra_{qual}"]),
            "tabela": int(r[f"tabela_{qual}"]),
            "peso": None if pd.isna(peso) else round(float(peso), 4),
        }

    def item_de(codigo: str, nivel: str) -> str:
        return codigo[:4] if nivel == "subitem" else codigo[:2] if nivel == "item" else codigo[:1]

    grupos = []
    for indices in _grupos(mapa):
        linhas = mapa.loc[indices].sort_values(["codigo_ibge_origem", "codigo_ibge_destino"])
        primeira = linhas.iloc[0]
        tabela_o, tabela_d = int(primeira.tabela_origem), int(primeira.tabela_destino)
        nivel = primeira.nivel_hierarquico
        itens = sorted(
            {
                item_de(c, nivel)
                for c in [*linhas.codigo_ibge_origem, *linhas.codigo_ibge_destino]
                if c
            }
        )
        # Contexto: o que sai e entra sem candidato nos mesmos itens, na mesma troca.
        auto = mapa[
            (mapa.situacao == "automatico")
            & mapa.tipo_correspondencia.isin(["descontinuado", "novo"])
            & (mapa.nivel_hierarquico == nivel)
            & (
                (mapa.tabela_origem == tabela_o)
                | (mapa.tabela_destino == tabela_d) & mapa.tabela_origem.isna()
            )
        ]
        contexto = []
        for _, r in auto.iterrows():
            codigo = (
                r.codigo_ibge_origem if pd.notna(r.codigo_sidra_origem) else r.codigo_ibge_destino
            )
            if item_de(codigo, nivel) in itens:
                contexto.append(
                    {
                        "tipo": r.tipo_correspondencia,
                        "codigo": codigo,
                        "nome": r.nome_origem
                        if r.tipo_correspondencia == "descontinuado"
                        else r.nome_destino,
                    }
                )
        grupos.append(
            {
                "transicao": f"POF {pofs[tabela_o]} → {pofs[tabela_d]}",
                "tabelas": f"{tabela_o} → {tabela_d}",
                "nivel": nivel,
                "itens": [
                    {
                        "codigo": c,
                        "nome": nomes.get((tabela_d, c)) or nomes.get((tabela_o, c)) or "",
                    }
                    for c in itens
                ],
                "ligacoes": [
                    {
                        "id": id_ligacao(r),
                        "tipo": r.tipo_correspondencia,
                        "criterio": r.criterio,
                        "origem": lado(r, "origem"),
                        "destino": lado(r, "destino"),
                    }
                    for _, r in linhas.iterrows()
                ],
                "contexto": sorted(contexto, key=lambda c: (c["tipo"], c["codigo"])),
            }
        )
    grupos.sort(key=lambda g: (g["tabelas"], g["itens"][0]["codigo"] if g["itens"] else ""))
    return {"indice": indice.nome, "codigo": indice.codigo, "grupos": grupos}


CSS_REVISAO = """
.painel { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5; background: var(--papel); padding-block: 10px; border-bottom: 1px solid var(--linha); display: grid; gap: 10px; }
body::before { content: ""; position: fixed; inset: 0 0 auto; height: env(safe-area-inset-top, 0px); z-index: 10; background: var(--papel); }
.contadores { display: flex; flex-wrap: wrap; gap: 6px 18px; font-variant-numeric: tabular-nums; }
.contadores b { font-size: 1.05rem; }
.barra-progresso { height: 6px; border-radius: 3px; background: var(--nao-fundo); overflow: hidden; display: flex; }
.barra-progresso span { display: block; height: 100%; }
.barra-progresso .aceitas { background: var(--sim); } .barra-progresso .rejeitadas { background: var(--falha); }
.aviso { background: var(--alerta-fundo); border: 1px solid var(--linha); border-radius: 6px; padding: 10px 14px; }
.grupos { display: grid; gap: 16px; }
.grupo { background: var(--superficie); border: 1px solid var(--linha); border-radius: 8px; padding: 14px 16px; display: grid; gap: 12px; min-width: 0; }
.grupo-topo { display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: baseline; justify-content: space-between; }
.grupo-topo h3 { font-size: 1.05rem; }
.ligacao { border-top: 1px solid var(--linha); padding-top: 10px; display: grid; gap: 8px; }
.ligacao.aceita { box-shadow: inset 4px 0 0 var(--sim); padding-left: 10px; }
.ligacao.rejeitada { box-shadow: inset 4px 0 0 var(--falha); padding-left: 10px; }
.par { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: 10px; align-items: start; }
.lado { display: grid; gap: 2px; min-width: 0; }
.lado .nome { font-weight: 600; }
.lado small { font-family: var(--fonte-dados); }
.seta-par { font-family: var(--fonte-dados); color: var(--suave); padding-top: 2px; }
.acoes { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
button.acao { font: inherit; font-size: 0.9rem; padding: 6px 14px; border-radius: 6px; border: 1px solid var(--linha); background: var(--superficie); color: var(--tinta); cursor: pointer; }
button.acao.aceitar { border-color: var(--sim); color: var(--sim); } button.acao.aceitar[aria-pressed="true"] { background: var(--sim); color: var(--papel); }
button.acao.rejeitar { border-color: var(--falha); color: var(--falha); } button.acao.rejeitar[aria-pressed="true"] { background: var(--falha); color: var(--papel); }
button.acao:disabled { opacity: 0.5; cursor: not-allowed; }
.observacao { display: grid; gap: 6px; }
.observacao textarea { font: inherit; width: 100%; min-height: 4.5em; padding: 8px; border: 1px solid var(--linha); border-radius: 6px; background: var(--papel); color: var(--tinta); resize: vertical; }
.situacao-texto { color: var(--suave); font-size: 0.88rem; }
.contexto { font-size: 0.88rem; color: var(--suave); }
.contexto b { color: var(--tinta); }
@media (max-width: 560px) { .par { grid-template-columns: 1fr; } .seta-par { transform: rotate(90deg); justify-self: start; } }
"""

JS_REVISAO = """
const dados = JSON.parse(document.getElementById('dados').textContent);
const ligacoes = dados.grupos.flatMap((g) => g.ligacoes.map((l) => ({...l, grupo: g})));
const decisoes = {};
const rascunhos = {};
let db = null;
let meuId = null;
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const aviso = document.getElementById('aviso');
const mostrarAviso = (texto) => { aviso.textContent = texto; aviso.hidden = !texto; };

function lado(l) {
  if (!l) return '<div class="lado"><span class="situacao-texto">(nada)</span></div>';
  const peso = l.peso === null ? 'sem peso' : 'peso ' + String(l.peso).replace('.', ',');
  return `<div class="lado"><span class="nome">${esc(l.nome)}</span><small>${esc(l.codigo)} · id ${l.id} · tabela ${l.tabela} · ${peso}</small></div>`;
}

function montar() {
  const raiz = document.getElementById('grupos');
  raiz.innerHTML = dados.grupos.map((g, gi) => `
    <article class="grupo" data-grupo="${gi}" data-transicao="${esc(g.transicao)}">
      <div class="grupo-topo">
        <h3>${g.itens.map((i) => esc(i.codigo + ' ' + i.nome)).join(' · ')}</h3>
        <span class="situacao-texto">${esc(g.transicao)} (${esc(g.tabelas)}) · ${esc(g.nivel)}</span>
      </div>
      ${g.ligacoes.map((l) => `
        <div class="ligacao" id="lig-${esc(l.id)}" data-id="${esc(l.id)}">
          <div class="par">${lado(l.origem)}<span class="seta-par">→</span>${lado(l.destino)}</div>
          <div><span class="selo estrutural">${esc(l.tipo)}</span> <span class="situacao-texto">${esc(dados.explicacao[l.tipo] || '')}</span></div>
          <div class="situacao-texto">Por que foi proposta: ${esc(l.criterio)} · <code>${esc(l.id)}</code></div>
          <div class="acoes">
            <button type="button" class="acao aceitar" id="aceitar-${esc(l.id)}" aria-pressed="false">Aceitar</button>
            <button type="button" class="acao rejeitar" id="rejeitar-${esc(l.id)}" aria-pressed="false">Não aceitar</button>
            <button type="button" class="acao desfazer" id="desfazer-${esc(l.id)}" hidden>Desfazer</button>
            <span class="situacao-texto estado"></span>
          </div>
          <div class="observacao" hidden>
            <label for="obs-${esc(l.id)}">Por que não aceitar? (ex.: é quebra; o certo é fundir com outro subitem)</label>
            <textarea id="obs-${esc(l.id)}"></textarea>
            <div class="acoes"><button type="button" class="acao rejeitar salvar" id="salvar-${esc(l.id)}">Salvar como não aceita</button></div>
          </div>
        </div>`).join('')}
      ${g.contexto.length ? `<div class="contexto">No mesmo item, sem candidato: ${g.contexto.map((c) => `<b>${c.tipo === 'novo' ? 'entra' : 'sai'}</b> ${esc(c.codigo + ' ' + c.nome)}`).join('; ')}</div>` : ''}
    </article>`).join('');

  raiz.querySelectorAll('.ligacao').forEach((el) => {
    const id = el.dataset.id;
    const obs = el.querySelector('.observacao');
    const area = el.querySelector('textarea');
    area.addEventListener('input', () => { rascunhos[id] = area.value; });
    el.querySelector('.aceitar').addEventListener('click', () => salvar(id, 'aceita', ''));
    el.querySelector('.rejeitar:not(.salvar)').addEventListener('click', () => {
      obs.hidden = false;
      area.value = rascunhos[id] ?? decisoes[id]?.observacao ?? '';
      area.focus();
    });
    el.querySelector('.salvar').addEventListener('click', () => {
      const texto = area.value.trim();
      if (!texto) { mostrarAviso('Escreva uma observação para registrar por que a proposta não foi aceita.'); area.focus(); return; }
      salvar(id, 'rejeitada', texto);
    });
    el.querySelector('.desfazer').addEventListener('click', () => desfazer(id));
  });
}

function atualizar() {
  let aceitas = 0, rejeitadas = 0;
  document.querySelectorAll('.ligacao').forEach((el) => {
    const d = decisoes[el.dataset.id];
    el.classList.toggle('aceita', d?.decisao === 'aceita');
    el.classList.toggle('rejeitada', d?.decisao === 'rejeitada');
    el.querySelector('.aceitar').setAttribute('aria-pressed', String(d?.decisao === 'aceita'));
    el.querySelector('.rejeitar:not(.salvar)').setAttribute('aria-pressed', String(d?.decisao === 'rejeitada'));
    el.querySelector('.desfazer').hidden = !d;
    el.querySelectorAll('button').forEach((b) => { b.disabled = !db; });
    el.querySelector('.estado').textContent = d ? (d.decisao === 'aceita' ? 'Aceita' : 'Não aceita: ' + d.observacao) : '';
    if (d?.decisao === 'rejeitada' || d?.decisao === 'aceita') el.querySelector('.observacao').hidden = true;
    if (d?.decisao === 'aceita') aceitas++; else if (d?.decisao === 'rejeitada') rejeitadas++;
  });
  const total = ligacoes.length;
  document.getElementById('n-total').textContent = total;
  document.getElementById('n-aceitas').textContent = aceitas;
  document.getElementById('n-rejeitadas').textContent = rejeitadas;
  document.getElementById('n-pendentes').textContent = total - aceitas - rejeitadas;
  document.querySelector('.barra-progresso .aceitas').style.width = (100 * aceitas / total) + '%';
  document.querySelector('.barra-progresso .rejeitadas').style.width = (100 * rejeitadas / total) + '%';
  filtrar();
}

async function salvar(id, decisao, observacao) {
  if (!db) return;
  mostrarAviso('');
  try {
    await db.collection('decisoes').doc(id).set({decisao, observacao, em: new Date().toISOString(), por: meuId});
  } catch (e) {
    mostrarAviso('Não foi possível salvar a decisão (' + (e.message || e.code) + '). Tente de novo.');
  }
}

async function desfazer(id) {
  if (!db) return;
  try { await db.collection('decisoes').doc(id).delete(); delete rascunhos[id]; }
  catch (e) { mostrarAviso('Não foi possível desfazer (' + (e.message || e.code) + ').'); }
}

let transicao = 'todas';
let estado = 'todas';
function filtrar() {
  const termo = document.getElementById('busca').value.toLowerCase();
  document.querySelectorAll('.grupo').forEach((g) => {
    let algum = false;
    g.querySelectorAll('.ligacao').forEach((el) => {
      const d = decisoes[el.dataset.id]?.decisao || 'pendente';
      const ok = (estado === 'todas' || estado === d) && (!termo || g.textContent.toLowerCase().includes(termo));
      el.hidden = !ok; algum = algum || ok;
    });
    g.hidden = !algum || (transicao !== 'todas' && g.dataset.transicao !== transicao);
  });
}
document.querySelectorAll('[data-filtro-transicao]').forEach((b) => b.addEventListener('click', () => {
  transicao = b.dataset.filtroTransicao;
  document.querySelectorAll('[data-filtro-transicao]').forEach((o) => o.classList.toggle('ativa', o === b));
  filtrar();
}));
document.querySelectorAll('[data-filtro-estado]').forEach((b) => b.addEventListener('click', () => {
  estado = b.dataset.filtroEstado;
  document.querySelectorAll('[data-filtro-estado]').forEach((o) => o.classList.toggle('ativa', o === b));
  filtrar();
}));
document.getElementById('busca').addEventListener('input', filtrar);

montar();
atualizar();
mostrarAviso('Conectando ao banco de decisões...');
(async () => {
  db = await claude.use('db');
  if (!db) { mostrarAviso('As decisões não podem ser salvas nesta visualização. Abra a página em claude.ai, conectado à sua conta.'); atualizar(); return; }
  const user = await claude.use('user');
  meuId = user ? await user.id() : null;
  mostrarAviso('');
  db.collection('decisoes').onSnapshot((snap) => {
    for (const k of Object.keys(decisoes)) delete decisoes[k];
    snap.docs.forEach((d) => { decisoes[d.id] = d.data(); });
    atualizar();
  }, (e) => mostrarAviso('Erro ao ler as decisões (' + (e.message || e.code) + ').'));
})();
"""


def renderizar(dados: dict) -> str:
    dados = {**dados, "explicacao": EXPLICACAO_TIPO}
    json_dados = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")
    transicoes = sorted({g["transicao"] for g in dados["grupos"]})
    n_ligacoes = sum(len(g["ligacoes"]) for g in dados["grupos"])
    botoes = "".join(
        f'<button type="button" class="aba" data-filtro-transicao="{escape(t)}" id="tr-{i}">{escape(t)}</button>'
        for i, t in enumerate(transicoes)
    )
    return f"""<title>Revisão da harmonização do {escape(dados["indice"])}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Sans:ital,wght@0,400;0,600;1,400&display=swap">
<style>{CSS}{CSS_REVISAO}</style>
<main class="pagina">
  <header class="topo">
    <span class="olho">Macroeconomia da Agricultura Familiar · {escape(dados["codigo"])} · issue #6</span>
    <h1>Revisão da harmonização do {escape(dados["indice"])}</h1>
    <p>Cada cartão liga categorias de uma tabela do IBGE às da tabela seguinte, depois de uma troca de POF. As regras não tinham prova suficiente para ligar sozinhas; por isso, até você decidir, cada ligação conta como <b>quebra</b> na série longa. <b>Aceitar</b> confirma a ligação. <b>Não aceitar</b> mantém a quebra e pede uma observação. As ligações que tocam as mesmas categorias aparecem juntas no mesmo cartão: revise o cartão inteiro.</p>
    <p class="situacao-texto">{n_ligacoes} ligações em {len(dados["grupos"])} cartões. As decisões ficam salvas nesta página; o Claude as lê e grava no mapa do repositório.</p>
  </header>
  <div class="painel">
    <div class="contadores" aria-live="polite">
      <span><b id="n-pendentes">0</b> pendentes</span><span><b id="n-aceitas">0</b> aceitas</span><span><b id="n-rejeitadas">0</b> não aceitas</span><span>de <b id="n-total">0</b></span>
    </div>
    <div class="barra-progresso" aria-hidden="true"><span class="aceitas"></span><span class="rejeitadas"></span></div>
    <div class="controles">
      <label for="busca">Buscar:</label><input type="search" id="busca" placeholder="nome ou código">
      <div class="abas" role="group" aria-label="Troca de POF"><button type="button" class="aba ativa" data-filtro-transicao="todas" id="tr-todas">Todas as trocas</button>{botoes}</div>
      <div class="abas" role="group" aria-label="Situação">
        <button type="button" class="aba ativa" data-filtro-estado="todas" id="st-todas">Todas</button>
        <button type="button" class="aba" data-filtro-estado="pendente" id="st-pendente">Pendentes</button>
        <button type="button" class="aba" data-filtro-estado="aceita" id="st-aceita">Aceitas</button>
        <button type="button" class="aba" data-filtro-estado="rejeitada" id="st-rejeitada">Não aceitas</button>
      </div>
    </div>
    <div id="aviso" class="aviso" role="status" hidden></div>
  </div>
  <section id="grupos" class="grupos"></section>
</main>
<script type="application/json" id="dados">{json_dados}</script>
<script>{JS_REVISAO}</script>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera a página de revisão da harmonização.")
    parser.add_argument("--indice", default="ipca15")
    args = parser.parse_args(argv)
    indice = carregar_catalogo().indices[args.indice]
    destino = caminho_pagina(indice)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(renderizar(coletar(indice)), encoding="utf-8")
    print(f"{destino.relative_to(RAIZ)} gerada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
