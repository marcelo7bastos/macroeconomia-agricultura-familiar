// Explicação do café: tudo vem de DADOS (marts conferidos pelo hash); nada de rede.
const $ = id => document.getElementById(id);
const NOMES_MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const mesCurto = m => NOMES_MES[+m.slice(5) - 1] + "/" + m.slice(0, 4);
const MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const mesLongo = m => MESES_LONGOS[+m.slice(5) - 1] + " de " + m.slice(0, 4);
const num = (v, casas = 1) => v == null ? "—" : v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
const pct = (v, casas = 1) => v == null ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + num(Math.abs(v), casas) + "%";
const S = DADOS.series;
const fim = DADOS.meses.indexOf(DADOS.fim) + 1;
const meses = DADOS.meses.slice(0, fim);
const corte = a => a.slice(0, fim);
const ult = (id, campo) => S[id][campo][fim - 1];

// ---------------------------------------------------------------- textos
document.querySelectorAll("[data-base]").forEach(e => e.textContent = mesCurto(DADOS.base));
document.querySelectorAll("[data-fim]").forEach(e => e.textContent = mesLongo(DADOS.fim));
$("olho").textContent = `Piloto do café · IPCA × mercado internacional · dados até ${mesCurto(DADOS.fim)}`;
const pico = DADOS.defasagens.cafe_arabica_fmi.variacao_mensal.reduce((m, v, i, a) => v > a[m] ? i : m, 0);
$("abre").innerHTML =
  `Em 12 meses até ${mesLongo(DADOS.fim)}, o preço internacional do café em reais variou <b>${pct(ult("cafe_arabica_fmi", "variacao_acum_12m"))}</b> (arábica) e ` +
  `<b>${pct(ult("cafe_robusta_fmi", "variacao_acum_12m"))}</b> (robusta). No IPCA, o <b>café moído</b> variou ${pct(ult("ipca_cafe_moido", "variacao_acum_12m"))} e o ` +
  `<b>cafezinho</b>, servido fora de casa, ${pct(ult("ipca_cafezinho", "variacao_acum_12m"))}. A correlação entre o arábica e o café moído é maior com ` +
  `<b>${pico} ${pico === 1 ? "mês" : "meses"} de atraso</b>.`;
$("nota-fontes").textContent =
  `FMI e Banco Mundial divergem menos de ${num(DADOS.limite_pct, 0)}% em quase todos os meses desde ${DADOS.base.slice(0, 4)}. ` +
  `Os ${DADOS.excecoes} meses acima disso estão registrados como exceções, sem ajuste.`;
$("rodape-dados").innerHTML =
  `Coleta mais recente: ${DADOS.coleta.slice(0, 10)} · dados em <a href="../../data/marts/cafe_mensal.csv">cafe_mensal.csv</a> e ` +
  `<a href="../../data/marts/cafe_defasagens.csv">cafe_defasagens.csv</a> · <a href="../../data/marts/cafe_README.md">dicionário</a> · ` +
  `<a href="${DADOS.repositorio}">repositório</a>`;

const cartoes = [
  ["s1", "Arábica, em R$", "cafe_arabica_fmi", `R$ ${num(ult("cafe_arabica_fmi", "preco_brl_saca"), 0)} a saca de 60 kg`],
  ["s2", "Robusta, em R$", "cafe_robusta_fmi", `R$ ${num(ult("cafe_robusta_fmi", "preco_brl_saca"), 0)} a saca de 60 kg`],
  ["s3", "Café moído (IPCA)", "ipca_cafe_moido", `${pct(ult("ipca_cafe_moido", "variacao_mensal"), 2)} em ${NOMES_MES[+DADOS.fim.slice(5) - 1]}`],
  ["s4", "Cafezinho (IPCA)", "ipca_cafezinho", `${pct(ult("ipca_cafezinho", "variacao_mensal"), 2)} em ${NOMES_MES[+DADOS.fim.slice(5) - 1]}`],
];
$("numeros").innerHTML = cartoes.map(([cor, rotulo, id, nota]) => {
  const v = ult(id, "variacao_acum_12m");
  return `<div class="numero"><div class="rotulo"><i class="${cor}"></i>${rotulo}</div>` +
    `<div class="valor ${v > 0 ? "sobe" : "desce"}">${pct(v)}</div><div class="nota">${nota}</div></div>`;
}).join("");
$("numeros").setAttribute("aria-label", `Variação em 12 meses até ${mesLongo(DADOS.fim)}`);

// ---------------------------------------------------------------- gráficos
const L = 60, R = 12, T = 10, B = 28, W = 860;
const dica = $("dica");

function escala(min, max, n = 5) {
  const passo0 = (max - min) / n, pot = 10 ** Math.floor(Math.log10(passo0));
  const passo = [1, 2, 2.5, 5, 10].map(m => m * pot).find(p => p >= passo0);
  const ini = Math.floor(min / passo) * passo, fimE = Math.ceil(max / passo) * passo;
  const marcas = [];
  for (let v = ini; v <= fimE + passo / 2; v += passo) marcas.push(+v.toFixed(10));
  return { ini, fim: fimE, marcas };
}

function mostrarDica(evento, titulo, linhas) {
  dica.innerHTML = `<b>${titulo}</b>` + linhas.map(([cor, txt]) => `<div><i class="${cor}"></i>${txt}</div>`).join("");
  dica.hidden = false;
  const r = dica.getBoundingClientRect();
  let x = evento.clientX + 14, y = evento.clientY + 14;
  if (x + r.width > innerWidth - 8) x = evento.clientX - r.width - 14;
  if (y + r.height > innerHeight - 8) y = evento.clientY - r.height - 14;
  dica.style.left = Math.max(8, x) + "px";
  dica.style.top = Math.max(8, y) + "px";
}
const esconderDica = () => { dica.hidden = true; };

function linhas(alvo, series, formato, { zero = false, H = 320 } = {}) {
  const valores = series.flatMap(s => s.dados).filter(v => v != null);
  const esc = escala(Math.min(...valores, zero ? 0 : Infinity), Math.max(...valores));
  const n = meses.length, x = i => L + (W - L - R) * i / (n - 1);
  const y = v => T + (H - T - B) * (1 - (v - esc.ini) / (esc.fim - esc.ini));
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${alvo.dataset.rotulo || ""}">`;
  esc.marcas.forEach(v => {
    svg += `<line class="grade" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/>`;
    svg += `<text x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${formato.eixo(v)}</text>`;
  });
  if (zero && esc.ini < 0) svg += `<line class="zero" x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}"/>`;
  const passoRotulo = Math.ceil(n / 7);
  for (let i = 0; i < n; i += passoRotulo) svg += `<text x="${x(i)}" y="${H - 8}" text-anchor="middle">${mesCurto(meses[i])}</text>`;
  svg += `<line class="eixo" x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}"/>`;
  series.forEach(s => {
    let d = "", aberto = false;
    s.dados.forEach((v, i) => {
      if (v == null) { aberto = false; return; }
      d += `${aberto ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`; aberto = true;
    });
    svg += `<path d="${d}" fill="none" style="stroke:var(--${s.cor})" stroke-width="2" stroke-linejoin="round"/>`;
  });
  svg += `<line class="mira" x1="0" x2="0" y1="${T}" y2="${H - B}" visibility="hidden"/>`;
  series.forEach(s => svg += `<circle class="ponto" r="4" style="fill:var(--${s.cor});stroke:var(--surface)" stroke-width="2" visibility="hidden"/>`);
  svg += `<rect x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent" style="cursor:crosshair"/></svg>`;
  alvo.innerHTML = svg;
  const el = alvo.querySelector("svg"), mira = el.querySelector(".mira"), pontos = el.querySelectorAll(".ponto");
  el.querySelector("rect").addEventListener("pointermove", ev => {
    const caixa = el.getBoundingClientRect(), px = (ev.clientX - caixa.left) * W / caixa.width;
    const i = Math.max(0, Math.min(n - 1, Math.round((px - L) / (W - L - R) * (n - 1))));
    mira.setAttribute("x1", x(i)); mira.setAttribute("x2", x(i)); mira.setAttribute("visibility", "visible");
    series.forEach((s, k) => {
      const v = s.dados[i];
      pontos[k].setAttribute("visibility", v == null ? "hidden" : "visible");
      if (v != null) { pontos[k].setAttribute("cx", x(i)); pontos[k].setAttribute("cy", y(v)); }
    });
    mostrarDica(ev, mesCurto(meses[i]), series.map(s => [s.cor, `${s.nome}: ${formato.dica(s.dados[i])}`]));
  });
  el.querySelector("rect").addEventListener("pointerleave", () => {
    mira.setAttribute("visibility", "hidden"); pontos.forEach(p => p.setAttribute("visibility", "hidden")); esconderDica();
  });
}

function barras(alvo, series, rotulos, { H = 300 } = {}) {
  const valores = series.flatMap(s => s.dados);
  const esc = escala(Math.min(0, ...valores), Math.max(...valores));
  const n = rotulos.length, faixa = (W - L - R) / n, larg = faixa * 0.7 / series.length;
  const y = v => T + (H - T - B) * (1 - (v - esc.ini) / (esc.fim - esc.ini));
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Correlação por defasagem">`;
  esc.marcas.forEach(v => {
    svg += `<line class="grade" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/>`;
    svg += `<text x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${num(v, 1)}</text>`;
  });
  svg += `<line class="zero" x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}"/>`;
  rotulos.forEach((r, i) => {
    const x0 = L + faixa * i + faixa * 0.15;
    series.forEach((s, k) => {
      const v = s.dados[i], topo = Math.min(y(v), y(0)), alt = Math.max(1, Math.abs(y(v) - y(0)));
      svg += `<rect x="${(x0 + k * larg + 1).toFixed(1)}" y="${topo.toFixed(1)}" width="${(larg - 2).toFixed(1)}" height="${alt.toFixed(1)}" rx="3" style="fill:var(--${s.cor})"/>`;
    });
    if (i % 2 === 0 || n <= 8) svg += `<text x="${L + faixa * (i + 0.5)}" y="${H - 8}" text-anchor="middle">${r}</text>`;
    svg += `<rect class="alvo" data-i="${i}" x="${L + faixa * i}" y="${T}" width="${faixa}" height="${H - T - B}" fill="transparent"/>`;
  });
  alvo.innerHTML = svg + "</svg>";
  alvo.querySelectorAll(".alvo").forEach(r => {
    r.addEventListener("pointermove", ev => {
      const i = +r.dataset.i;
      mostrarDica(ev, `Defasagem: ${i === 0 ? "mesmo mês" : i + (i === 1 ? " mês" : " meses")}`, series.map(s => [s.cor, `${s.nome}: ${num(s.dados[i], 2)}`]));
    });
    r.addEventListener("pointerleave", esconderDica);
  });
}

const fmtIndice = { eixo: v => num(v, 0), dica: v => num(v, 1) };
const fmtPct = { eixo: v => num(v, 0) + "%", dica: v => pct(v) };
const fmtReal = { eixo: v => "R$ " + num(v, 0), dica: v => v == null ? "—" : "R$ " + num(v, 0) };

linhas($("g-indice"), [
  { nome: "Arábica (R$)", cor: "s1", dados: corte(S.cafe_arabica_fmi.indice_base_100) },
  { nome: "Robusta (R$)", cor: "s2", dados: corte(S.cafe_robusta_fmi.indice_base_100) },
  { nome: "Café moído", cor: "s3", dados: corte(S.ipca_cafe_moido.indice_base_100) },
], fmtIndice);

linhas($("g-12m"), [
  { nome: "Arábica (R$)", cor: "s1", dados: corte(S.cafe_arabica_fmi.variacao_acum_12m) },
  { nome: "Café moído", cor: "s3", dados: corte(S.ipca_cafe_moido.variacao_acum_12m) },
  { nome: "Cafezinho", cor: "s4", dados: corte(S.ipca_cafezinho.variacao_acum_12m) },
], fmtPct, { zero: true });

function desenharDefasagem(medida) {
  const d = DADOS.defasagens;
  const rotulos = d.cafe_arabica_fmi[medida].map((_, i) => i === 0 ? "mesmo mês" : i + (i === 1 ? " mês" : " meses"));
  barras($("g-defasagem"), [
    { nome: "Arábica", cor: "s1", dados: d.cafe_arabica_fmi[medida] },
    { nome: "Robusta", cor: "s2", dados: d.cafe_robusta_fmi[medida] },
  ], rotulos);
}
function desenharSaca(campo) {
  linhas($("g-saca"), [
    { nome: "Arábica", cor: "s1", dados: corte(S.cafe_arabica_fmi[campo]) },
    { nome: "Robusta", cor: "s2", dados: corte(S.cafe_robusta_fmi[campo]) },
  ], fmtReal);
}
desenharDefasagem("variacao_mensal");
desenharSaca("preco_brl_saca");

function chave(ids, ativo, acao) {
  ids.forEach(id => $(id).setAttribute("aria-pressed", String(id === ativo)));
  acao();
}
$("b-mensal").onclick = () => chave(["b-mensal", "b-anual"], "b-mensal", () => desenharDefasagem("variacao_mensal"));
$("b-anual").onclick = () => chave(["b-mensal", "b-anual"], "b-anual", () => desenharDefasagem("variacao_acum_12m"));
$("b-nominal").onclick = () => chave(["b-nominal", "b-real"], "b-nominal", () => desenharSaca("preco_brl_saca"));
$("b-real").onclick = () => chave(["b-nominal", "b-real"], "b-real", () => desenharSaca("preco_real_brl_saca"));

// ---------------------------------------------------------------- tabela
const linhasTabela = [];
for (let i = fim - 1; i >= Math.max(0, fim - 12); i--) {
  linhasTabela.push(`<tr><td>${mesCurto(meses[i])}</td>` +
    `<td>${num(S.cafe_arabica_fmi.preco_brl_saca[i], 0)}</td><td>${num(S.cafe_robusta_fmi.preco_brl_saca[i], 0)}</td>` +
    `<td>${pct(S.cafe_arabica_fmi.variacao_acum_12m[i])}</td><td>${pct(S.ipca_cafe_moido.variacao_mensal[i], 2)}</td>` +
    `<td>${pct(S.ipca_cafe_moido.variacao_acum_12m[i])}</td><td>${pct(S.ipca_cafezinho.variacao_acum_12m[i])}</td></tr>`);
}
$("t-corpo").innerHTML = linhasTabela.join("");
