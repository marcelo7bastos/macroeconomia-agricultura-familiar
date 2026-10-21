'use strict';
const base=JSON.parse(document.getElementById('base-dados').textContent);
const $=id=>document.getElementById(id);
const texto=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const numero=(v,casas=2)=>v===null||v===undefined?'—':new Intl.NumberFormat('pt-BR',{minimumFractionDigits:casas,maximumFractionDigits:casas}).format(v);
const inteiro=v=>new Intl.NumberFormat('pt-BR').format(v);
const coleta=new Date(base.coleta).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'})+' (Brasília)';
const mesNome=m=>new Date(`${m}-15T12:00:00`).toLocaleDateString('pt-BR',{month:'short',year:'numeric'});
const github=caminho=>caminho.startsWith('src/')?`${base.repositorio}/blob/main/${caminho}`:`../../${caminho}`;
const nomes={'0':'Índice geral','1':'Alimentação e bebidas','11':'No domicílio','12':'Fora do domicílio'};
const cores={'0':'#17614f','1':'#bd502e'};
const codigoExemplo=base.tabelas.filter(t=>t.papel==='dados').at(-1).id+'.7169';
$('exemplo-chave').textContent=codigoExemplo;
document.querySelector(`[data-indice="${base.codigo}"]`).setAttribute('aria-current','page');
$('cobertura').textContent=`Detalhe: ${mesNome(base.inicio)} a ${mesNome(base.fim)} · última coleta: ${coleta} · Brasil`;
$('retrato').innerHTML=[
 [inteiro(base.linhas),'observações mensais publicadas'],[inteiro(base.meses),'meses de detalhe'],
 [inteiro(base.subitens),'subitens no último mês'],['5 CSVs','contratos de consumo por índice']
].map(([v,r])=>`<article><strong>${texto(v)}</strong><span>${texto(r)}</span></article>`).join('');
function abrir(id,foco=false){
 if(!document.querySelector(`[aria-controls="${id}"]`))return;
 document.querySelectorAll('[role=tab]').forEach(t=>{const ativa=t.getAttribute('aria-controls')===id;t.setAttribute('aria-selected',String(ativa));t.tabIndex=ativa?0:-1;});
 document.querySelectorAll('[role=tabpanel]').forEach(p=>p.hidden=p.id!==id);
 if(foco)$(`aba-${id}`).focus();
 history.replaceState(null,'',`#${id}`);
}
const abas=[...document.querySelectorAll('[role=tab]')];
abas.forEach((t,i)=>{
 t.addEventListener('click',()=>abrir(t.getAttribute('aria-controls')));
 t.addEventListener('keydown',e=>{
  let alvo=null;
  if(e.key==='ArrowRight')alvo=(i+1)%abas.length;
  if(e.key==='ArrowLeft')alvo=(i+abas.length-1)%abas.length;
  if(e.key==='Home')alvo=0;
  if(e.key==='End')alvo=abas.length-1;
  if(alvo!==null){e.preventDefault();abrir(abas[alvo].getAttribute('aria-controls'),true);}
 });
});
document.querySelectorAll('[data-abrir]').forEach(b=>b.addEventListener('click',()=>abrir(b.dataset.abrir,true)));
window.addEventListener('hashchange',()=>abrir(location.hash.slice(1)));
if(location.hash)abrir(location.hash.slice(1));
const meses=[...new Set(base.registros.map(r=>r.mes))].sort();
const anos=[...new Set(meses.map(m=>m.slice(0,4)))].sort().reverse();
$('ano').innerHTML=anos.map(a=>`<option>${a}</option>`).join('');
function carregarMeses(ultimo=true){
 const doAno=meses.filter(m=>m.startsWith($('ano').value));
 const anterior=$('mes').value;
 $('mes').innerHTML=doAno.map(m=>`<option value="${m}">${mesNome(m)}</option>`).join('');
 $('mes').value=ultimo||!doAno.includes(anterior)?doAno.at(-1):anterior;
 atualizar();
}
function origem(v,o){return `${numero(v)}<small>${v===null?'indisponível':texto(o||'origem não informada')}</small>`;}
function grafico(){
 const regs=base.registros.filter(r=>r.mes.startsWith($('ano').value)&&['0','1'].includes(r.codigo_ibge));
 const ms=[...new Set(regs.map(r=>r.mes))].sort();
 const valores=regs.map(r=>r.variacao_mensal).filter(v=>v!==null);
 const min=Math.min(0,...valores)-.15,max=Math.max(0,...valores)+.15;
 const x=i=>68+i*730/Math.max(1,ms.length-1), y=v=>245-(v-min)/(max-min)*205;
 let svg='<svg viewBox="0 0 850 300" role="img" aria-labelledby="titulo-grafico desc-grafico"><title id="titulo-grafico">Variação mensal: geral e alimentação</title><desc id="desc-grafico">Percentuais publicados no ano selecionado. Consulte os números exatos na tabela e no CSV exportável.</desc>';
 for(let i=0;i<5;i++){
  const v=min+(max-min)*i/4;
  svg+=`<line x1="68" x2="800" y1="${y(v)}" y2="${y(v)}" stroke="#e3e9dc"/><text x="55" y="${y(v)+4}" text-anchor="end" fill="#536561" font-size="12">${numero(v,1)}%</text>`;
 }
 svg+=`<line x1="68" x2="800" y1="${y(0)}" y2="${y(0)}" stroke="#a6b89f" stroke-dasharray="4 4"/>`;
 ms.forEach((m,i)=>svg+=`<text x="${x(i)}" y="275" text-anchor="middle" fill="#536561" font-size="12">${m.slice(5)}</text>`);
 for(const c of ['0','1']){
  let anterior=null;
  ms.forEach((m,i)=>{
   const r=regs.find(a=>a.codigo_ibge===c&&a.mes===m);
   if(!r||r.variacao_mensal===null){anterior=null;return;}
   const p={x:x(i),y:y(r.variacao_mensal)};
   if(anterior)svg+=`<line x1="${anterior.x}" y1="${anterior.y}" x2="${p.x}" y2="${p.y}" stroke="${cores[c]}" stroke-width="2.6"/>`;
   svg+=`<circle cx="${p.x}" cy="${p.y}" r="4" fill="${cores[c]}"><title>${nomes[c]} · ${mesNome(m)}: ${numero(r.variacao_mensal)}%</title></circle>`;
   anterior=p;
  });
 }
 $('grafico').innerHTML=svg+'</svg>';
}
function atualizar(){
 const mes=$('mes').value;
 const linhas=base.registros.filter(r=>r.mes===mes);
 const recortes=['0','1','11','12'].map(c=>linhas.find(r=>r.codigo_ibge===c)).filter(Boolean);
 $('aviso-periodo').textContent=`Leitura de ${mesNome(mes)}. O ano tem ${meses.filter(m=>m.startsWith($('ano').value)).length} meses disponíveis nesta publicação. Sem projeção para os demais meses.`;
 $('cartoes').innerHTML=recortes.map(r=>`<article class="cartao"><h3>${nomes[r.codigo_ibge]}</h3><strong>${numero(r.variacao_mensal)}%</strong><small>variação no mês · oficial</small><p>No ano: ${numero(r.acum_ano)}% <span class="tag">${texto(r.origem_ano||'indisponível')}</span></p><p>12 meses: ${numero(r.acum_12m)}% <span class="tag">${texto(r.origem_12m||'indisponível')}</span></p></article>`).join('');
 $('numeros').innerHTML=recortes.map(r=>`<tr><td>${nomes[r.codigo_ibge]}</td><td>${numero(r.variacao_mensal)}</td><td>${origem(r.acum_ano,r.origem_ano)}</td><td>${origem(r.acum_12m,r.origem_12m)}</td><td>${numero(r.peso,4)}</td><td>${numero(r.contribuicao_pp,6)}</td></tr>`).join('');
 const grupos=linhas.filter(r=>r.codigo_ibge.length===1&&r.codigo_ibge!=='0').sort((a,b)=>Math.abs(b.contribuicao_pp??0)-Math.abs(a.contribuicao_pp??0));
 const maior=Math.max(.000001,...grupos.map(r=>Math.abs(r.contribuicao_pp??0)));
 $('contribuicoes').innerHTML=grupos.map(r=>`<div class="contrib-linha"><span>${texto(r.nome)}</span><div class="trilho"><div class="valor-barra ${r.contribuicao_pp<0?'negativa':''}" style="width:${Math.abs(r.contribuicao_pp??0)/maior*100}%"></div></div><strong>${numero(r.contribuicao_pp,4)}</strong></div>`).join('');
 grafico();
}
$('ano').addEventListener('change',()=>carregarMeses());
$('mes').addEventListener('change',atualizar);
$('restaurar').addEventListener('click',()=>{$('ano').value=base.fim.slice(0,4);carregarMeses();});
$('baixar').addEventListener('click',()=>{
 const regs=base.registros.filter(r=>r.mes.startsWith($('ano').value)&&['0','1','11','12'].includes(r.codigo_ibge));
 const cols=['mes','codigo_ibge','nome','variacao_mensal','peso','contribuicao_pp','acum_ano','origem_ano','acum_12m','origem_12m'];
 const csv=[cols.join(','),...regs.map(r=>cols.map(c=>'"'+String(r[c]??'').replaceAll('"','""')+'"').join(','))].join('\n');
 const url=URL.createObjectURL(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'}));
 const a=document.createElement('a');a.href=url;a.download=`${base.codigo}-geral-alimentos-${$('ano').value}.csv`;a.click();URL.revokeObjectURL(url);
});
const descricoes={categorias:['Classificação e limites das séries','chave_categoria'],mensal:['Oficiais, índice, contribuição mensal e sazonalidade','mes, chave_categoria'],acumulados:['Janelas acumuladas e suas origens','mes, chave_categoria'],contribuicoes:['Contribuições acumuladas em pontos percentuais','mes, chave_categoria'],difusao:['Percentual de subitens em alta, geral e grupos','mes, codigo_ibge']};
$('arquivos').innerHTML=Object.entries(descricoes).map(([n,[d,c]])=>`<tr><td><a href="../../data/marts/${base.codigo}_${n}.csv">${base.codigo}_${n}.csv</a></td><td>${d}</td><td><code>${c}</code></td></tr>`).join('');
const etapas=[
 ['Coletar','config/series.yaml e APIs do IBGE','Consulta metadados; baixa meses ausentes e revisa os três mais recentes nas tabelas abertas.','JSON gzip, revisões e manifesto','Rotina automática; mantenedor investiga divergências','src/macroaf/extract/atualizar.py'],
 ['Organizar','Raw e metadados de cada tabela','Deriva a hierarquia pelo código IBGE, tipa valores e alinha a referência à cobertura do detalhe.','Dimensão, fato e referência em staging','Código compartilhado, configurado por índice','src/macroaf/transform/ipca15.py'],
 ['Validar','Fato, referência e exceções específicas','Confronta pesos, reconciliação, acumulados e continuidade; confere contagens exatas de exceções.','Resultados de validação e bloqueio em caso de falha','Código verifica; diagnóstico humano decide como tratar anomalias','src/macroaf/validate/ipca15.py'],
 ['Harmonizar','Categorias e mapa entre POFs','Propõe correspondências. Continuidade exige evidência e meses adjacentes; casos incertos aguardam revisão.','Mapa e série longa com quebras explícitas','Código propõe; mantenedor revisa','src/macroaf/transform/harmonizacao.py'],
 ['Calcular','Série longa e valores oficiais','Prefere o oficial quando mede a mesma série; calcula índice, janelas, contribuições, difusão e sazonalidade.','Indicadores com origem e marcas de qualidade','Módulos compartilhados, sem fabricar oficial ausente','src/macroaf/indicators/calcular.py'],
 ['Publicar','Indicadores conferidos e contratos estáveis','Recompõe e confere antes de gravar CSVs, dicionário e metadados; gera relatórios.','Cinco CSVs, hashes e explicações','Rotina publica; gestor escolhe uso adequado','src/macroaf/marts/publicar.py']
];
$('etapas').innerHTML=etapas.map((e,i)=>`<button data-etapa="${i}" aria-pressed="${i===0}" aria-controls="detalhe-etapa">${i+1}. ${e[0]}</button>`).join('');
function etapa(i){
 const [nome,entrada,regra,saida,responsavel,arquivo]=etapas[i];
 $('detalhe-etapa').innerHTML=`<p class="sobretitulo">Etapa ${i+1} · função e responsabilidade</p><h3>${nome}</h3><dl class="etapa-dados"><div><dt>Entrada</dt><dd>${entrada}</dd></div><div><dt>Processamento</dt><dd>${regra}</dd></div><div><dt>Saída</dt><dd>${saida}</dd></div><div><dt>Responsável</dt><dd>${responsavel}</dd></div></dl><a href="${github(arquivo)}">Examinar a implementação: ${arquivo} ↗</a><p class="nota">O desenho apresenta funções lógicas. O comando completo harmoniza antes de chamar o publicador, que revalida os dados antes da gravação.</p>`;
 document.querySelectorAll('[data-etapa]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.etapa)===i)));
}
document.querySelectorAll('[data-etapa]').forEach(b=>b.addEventListener('click',()=>etapa(Number(b.dataset.etapa))));etapa(0);
$('comandos').textContent=`uv sync --all-groups --locked\nuv run python -m macroaf.pipeline --indice ${base.codigo}\nuv run python -m macroaf.pipeline --indice ${base.codigo} --forcar\nuv run python -m macroaf.relatorios.gestao --indice ${base.codigo}\nuv run pytest -v --durations=15`;
$('validacoes').innerHTML=base.validacoes.map(v=>`<tr><td><code>${texto(v.validacao)}</code></td><td>${inteiro(v.verificados)}</td><td>${inteiro(v.falhas)}</td><td>${inteiro(v.excecoes_aplicadas)}</td><td>${v.ok?'Verificação passou':'Falha registrada'}</td></tr>`).join('');
$('limites-indice').innerHTML=base.codigo==='ipca'?'<h3>Ressalvas específicas do IPCA</h3><p>952 respostas sem coleta ficam no raw, sem gerar observações artificiais. Quatro lacunas reais impedem continuidade automática.</p><p>A fonte apresenta anomalias diagnosticadas em pesos e acumulados, incluindo 239 valores anuais com evidência independente. Os oficiais permanecem no fato; acumulados calculados têm origem marcada quando substituem um valor incompatível.</p><p>O detalhe desta entrega começa em julho/2006. A referência do geral desde 1979 não equivale a categorias e pesos desde essa data.</p>':'<h3>Ressalvas específicas do IPCA-15</h3><p>Itens in natura da POF 1995-96 têm evidência de cesta variável. Contribuições dos subitens afetados não são apresentadas como comparáveis; a contribuição entra pelo item.</p><p>Há ruído e erros pontuais publicados, documentados e contados. Nove casos de harmonização não aceitos aguardam investigação, incluindo leite pasteurizado e longa vida.</p><p>Uma quebra limita a janela da série longa; sem evidência suficiente, o projeto mantém séries mais curtas.</p>';
const h=base.harmonizacao;
$('harmonizacao').textContent=`Mapa desta publicação: ${inteiro(h.automatico||0)} ligações automáticas, ${inteiro(h.proposto||0)} propostas pendentes, ${inteiro(h.revisado||0)} revisadas e aceitas, ${inteiro(h.rejeitado||0)} rejeitadas. Essas contagens são de ligações, não de séries ou observações.`;
$('proveniencia').textContent=`Último mês: ${base.fim}. Última coleta registrada: ${coleta}. Referência oficial do geral: tabela ${base.referencia}. O raw deste índice tem ${inteiro(base.raw)} arquivos registrados no manifesto.`;
$('fontes-tabelas').innerHTML=base.tabelas.map(t=>`<tr><td><a href="https://sidra.ibge.gov.br/tabela/${t.id}">${t.id} ↗</a></td><td>${texto(t.papel)}</td><td>${texto(t.inicio)} → ${texto(t.fim||'último mês publicado')}</td></tr>`).join('');
const links=[['Dicionário e colunas',`data/marts/${base.dicionario}`],['Metodologia e regras','docs/METODOLOGIA.md'],['Ficha do índice',`docs/indices/${base.codigo}.md`],['Metadados e SHA-256','data/metadata.json'],['Exceções diagnosticadas',`reference/excecoes_validacao_${base.codigo}.csv`],['Operação e recuperação','docs/OPERACAO.md'],['Skill explicar-conteudo — procedimento usado',null]];
$('links-fontes').innerHTML=links.map(([rotulo,c])=>`<li><a href="${c?github(c):'https://github.com/marcelo7bastos/minhas-skills/blob/main/skills/explicar-conteudo/SKILL.md'}">${rotulo} ↗</a>${c?'':' (biblioteca privada do mantenedor)'}</li>`).join('');
$('link-estrutura').href=github('docs/ESTRUTURA.md');$('link-registro').href=github('docs/gestao/registro-estudo.md');$('link-repo').href=base.repositorio;$('link-actions').href=base.repositorio+'/actions/workflows/atualizacao.yml';
$('imprimir').addEventListener('click',()=>window.print());
$('ano').value=base.fim.slice(0,4);carregarMeses();
