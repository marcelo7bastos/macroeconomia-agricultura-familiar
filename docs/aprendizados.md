# Aprendizados

Registro do que os agentes (e as pessoas) aprenderam trabalhando no projeto. É a memória de longo
prazo dos agentes: sessões na nuvem são descartadas, o git fica.

## Como funciona

1. Uma descoberta não óbvia vira entrada aqui pela skill `/aprender`.
2. Cada lição é **promovida** para a forma mais forte que couber:

   | Força | Destino | Quando |
   |---|---|---|
   | 1 | teste automatizado (`tests/`) | dá para verificar no código; bug vira teste de regressão |
   | 2 | validação no pipeline (`src/macroaf/validate/`) | é propriedade dos dados |
   | 3 | regra no `AGENTS.md` (raiz ou de pasta) | é conduta que vale em toda sessão |
   | 4 | ficha (`docs/indices/`, `docs/fontes/`) | é conhecimento sobre um índice ou fonte |

3. Mudanças em `AGENTS.md` e em decisões passam por PR revisado pelo mantenedor.
4. Se a lição muda como os dados são tratados, a regra resultante vai também para
   [`METODOLOGIA.md`](METODOLOGIA.md), citando o A-NNN.
5. O hook de início de sessão mostra os títulos das cinco lições mais recentes.

Entradas novas vão **no topo** do registro, com numeração crescente (`A-NNN`). Uma lição que deixou
de valer não é apagada: ganha a linha `**Substituída por:** A-NNN`.

## Registro

### A-012 · 2026-10-19 · Mesmo código IBGE, id SIDRA diferente entre POFs
- **Contexto:** revisão da `dim_classificacao` (#4).
- **O que aconteceu:** 87 códigos IBGE têm `codigo_sidra` diferente entre tabelas, sempre com o
  nome alterado (ex.: `1101073` é 7180 na 1646/1387 e 12222 na 1705/7062). Cada `codigo_sidra`,
  por outro lado, corresponde sempre ao mesmo código e nome.
  As mudanças vão de grafia ("(rajado))" → "(rajado)") a escopo ampliado (Refrigerante →
  Refrigerante e água mineral) e produto diferente (Leite pasteurizado → Leite longa vida).
- **Lição:** juntar valores por `(tabela, codigo_sidra)`, nunca só pelo código IBGE; na
  harmonização, código igual não garante categoria igual, e id diferente exige revisão manual.
- **Promovida para:** testes `test_codigo_sidra_identifica_sempre_a_mesma_categoria` e
  `test_mesmo_codigo_ibge_pode_ter_outro_codigo_sidra_entre_pofs`; contrato da
  `dim_classificacao` (id único por tabela); junção do `fato_ipca15` (#5); `METODOLOGIA.md`
  seção 2; ficha; pedido na #6.

### A-011 · 2026-10-19 · Tudo o que o staging consome precisa estar no raw
- **Contexto:** revisão da extração (#3).
- **O que aconteceu:** a primeira versão consultava os metadados e os descartava; a #4 dependeria da
  rede para montar a classificação, e o mesmo raw não garantiria os mesmos marts.
- **Lição:** guardar no raw toda resposta que a transformação usa (valores e metadados), gravar de
  forma atômica e conferir o raw inteiro contra o manifesto.
- **Promovida para:** decisão 0003 (item 2); testes `tests/test_raw_repositorio.py` e
  `test_metadados_vao_para_o_raw_sem_revisao_quando_so_a_periodicidade_avanca`.

### A-010 · 2026-10-19 · Subitem com `nivel = 0` na tabela 1387
- **Contexto:** reconferência das fichas na API (#3), pelo `explorador-sidra`.
- **O que aconteceu:** `4103031.Conjunto infantil` (id 12409) da 1387 vem com `nivel = 0`, o mesmo
  do índice geral e dos grupos nessa tabela; quem contava pelo `nivel` achava 383 subitens, e são 384.
- **Lição:** confirma a A-001 com um caso concreto; a contagem pelo código IBGE é a única confiável.
- **Promovida para:** `PLANEJAMENTO.md` 3.1 (contagens corrigidas); caso de teste pedido na #4.

### A-009 · 2026-10-19 · Variável declarada nos metadados pode vir vazia
- **Contexto:** reconferência das fichas na API (#3).
- **O que aconteceu:** a 1120 (acumulado em 12 meses) consta nos metadados da 1705 e da 7062, mas
  vem `...` em todas as categorias de 2012-02 a 2017-02 (1705) e de 2020-02 a 2020-12 (7062).
- **Lição:** variável listada nos metadados não garante dado. A transformação trata `...` como
  ausente (nunca zero) e o acumulado em 12 meses é calculado e conferido com a 3065.
- **Promovida para:** comentários em `config/series.yaml`; `PLANEJAMENTO.md` 3.1; ficha; validação
  pedida na #5.

### A-008 · 2026-10-19 · Limite de 50 mil valores por requisição no SIDRA
- **Contexto:** reconferência das fichas na API (#3).
- **O que aconteceu:** a API de valores conta variáveis × períodos × categorias (mesmo sem dado) e,
  acima de 50.000, devolve HTTP 400 em texto puro ("Quantidade de valores solicitados: ... excedeu o
  limite: 50000").
- **Lição:** o extrator pede um mês por requisição (cerca de 1.800 valores na 7062); o erro 400 é
  definitivo e não deve ser retentado.
- **Promovida para:** teste `test_erro_400_do_sidra_vira_erro_definitivo_sem_retentativa`; ficha
  `docs/fontes/ibge-sidra.md`.

### A-007 · 2026-10-19 · Troca de POF chega ao IPCA-15 um mês depois do IPCA
- **Contexto:** catálogo de séries (#2), conferindo as versões de POF por tabela.
- **O que aconteceu:** as estruturas novas entram no IPCA em jul/2006, jan/2012 e jan/2020, e no
  IPCA-15 em ago/2006, fev/2012 e fev/2020 (fontes na ficha; fev/2012 confirmado depois pelos metadados da 1705, em #3).
- **Lição:** ao montar o catálogo de outro índice de preços (IPCA cheio, INPC), não copie as datas
  do IPCA-15; confira o início de cada tabela pelos metadados.
- **Promovida para:** teste `test_ipca15_tabelas_e_pofs`; ficha `docs/indices/ipca15.md`;
  conferência automática do catálogo contra os metadados prevista na #3.

### A-006 · 2026-10-19 · Instruções em `AGENTS.md`; `CLAUDE.md` só importa
- **Contexto:** troca de `CLAUDE.md` por `AGENTS.md` (#22).
- **O que aconteceu:** `AGENTS.md` é lido por vários agentes de código, mas o Claude Code carrega
  `CLAUDE.md`. Duas cópias das regras divergiriam.
- **Lição:** as regras ficam só em `AGENTS.md`; cada `CLAUDE.md` contém apenas `@AGENTS.md`. Uma regra
  por pasta exige os dois arquivos na pasta: `AGENTS.md` com o conteúdo e `CLAUDE.md` com o import.
- **Promovida para:** `AGENTS.md` (seção "Aprendizado contínuo"); verificação no CI prevista na #1.

### A-005 · 2026-10-19 · `gh` sem GraphQL nas sessões na nuvem
- **Contexto:** levantamento das issues para a etapa 0 (#20).
- **O que aconteceu:** `gh issue list` e `gh label list` falham com HTTP 403 ("GitHub GraphQL is
  not available from Claude Code sessions").
- **Lição:** nas sessões na nuvem, use a API REST: `gh api repos/{dono}/{repo}/issues`,
  `gh api repos/{dono}/{repo}/labels` etc.
- **Promovida para:** `docs/AGENTES.md` (seção "Ambiente na nuvem").

### A-004 · 2026-10-19 · Rede da sessão na nuvem bloqueia as APIs do IBGE
- **Contexto:** etapa 0 (#20), ao conferir metadados da tabela 7062.
- **O que aconteceu:** `servicodados.ibge.gov.br` e `apisidra.ibge.gov.br` retornam 403 no proxy
  da sessão (política de rede do ambiente).
- **Lição:** antes de extrair dados numa sessão na nuvem, os dois domínios precisam estar em
  *Allowed domains* do ambiente. Sem isso, pare e avise; nunca simule dados. O runner do GitHub
  Actions tem rede própria e é testado na #3.
- **Promovida para:** ficha `docs/fontes/ibge-sidra.md` e `docs/AGENTES.md`.

### A-003 · 2026-10-19 · Planilhas por link quebram o pipeline
- **Contexto:** auditoria do modelo Power BI anterior (`PLANEJAMENTO.md`, 3.3).
- **O que aconteceu:** links de planilhas do Google Drive foram a principal fonte de fragilidade.
- **Lição:** fonte só por API oficial ou CSV versionado em `reference/`.
- **Promovida para:** `CLAUDE.md` (movida para `AGENTS.md` em #22).

### A-002 · 2026-10-19 · IPCA-15 tem classificação própria
- **Contexto:** auditoria do modelo Power BI anterior.
- **O que aconteceu:** o modelo reaproveitava a classificação do IPCA cheio e perdia categorias: em
  7062 há 367 subitens; no IPCA cheio (7060), 377.
- **Lição:** a classificação vem sempre dos metadados da própria tabela.
- **Promovida para:** ficha `docs/indices/ipca15.md`; teste de contagem de categorias previsto na #4.

### A-001 · 2026-10-19 · Campo `nivel` dos metadados não é estável
- **Contexto:** auditoria do modelo Power BI anterior.
- **O que aconteceu:** 7062/1705 começam em 0 = geral; 1646/1387 usam outra escala.
- **Lição:** derive a hierarquia pelo código IBGE no nome da categoria (1 dígito = grupo,
  2 = subgrupo, 4 = item, 7 = subitem).
- **Promovida para:** `CLAUDE.md` (movida para `AGENTS.md` em #22); teste previsto na #4.
