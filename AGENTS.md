# Instruções para agentes de IA

Leia `docs/PLANEJAMENTO.md` antes de começar qualquer tarefa; ele é a fonte das decisões do projeto.
Antes de mexer num índice ou numa fonte, leia a ficha dele em `docs/indices/` ou `docs/fontes/` e as
lições recentes em `docs/aprendizados.md`.

## Regras do projeto

- Idioma: português em código (nomes de variáveis, funções, colunas), comentários, docs, commits e issues.
- Piloto atual: **IPCA-15**. Outras frentes ficam como issues com o rótulo `backlog`; não implemente
  sem uma issue correspondente.
- Hierarquia da classificação 315 do SIDRA: derive pelo código IBGE no nome da categoria
  (1 dígito = grupo, 2 = subgrupo, 4 = item, 7 = subitem), nunca pelo campo `nivel` dos metadados.
- Prefira o dado oficial; só calcule o que o IBGE/BCB não publica. Todo indicador calculado precisa
  de teste contra referência oficial ou identidade contábil.
- Nunca emende séries de POFs diferentes em silêncio: use `map_harmonizacao` e marque quebras.
- Nomes de arquivos em `data/marts/` são estáveis (o Power BI lê pelas URLs do raw do GitHub).
- Fontes de dados só por API oficial ou CSV versionado em `reference/`; nada de links de planilhas.
- APIs usadas: `apisidra.ibge.gov.br` e `servicodados.ibge.gov.br`.
- O que muda entre índices é configuração (`config/series.yaml`) e ficha, não código nem agente.

## Fluxo de trabalho

- Uma issue por tarefa, um branch por issue, um PR por branch. O PR cita a issue (`Fecha #N`).
- Antes de abrir o PR, rode `/fechar-etapa` (testes, ruff, validações, revisão metodológica,
  documentação e aprendizados).
- Subagentes (`.claude/agents/`): `revisor-metodologico` antes de todo PR; `validador-dados` quando
  uma validação falhar; `explorador-sidra` para conhecer tabela ou índice novo. Veja `docs/AGENTES.md`.

## Aprendizado contínuo

- Ao descobrir algo não óbvio (erro, peculiaridade da API, decisão de método), registre com `/aprender`
  em `docs/aprendizados.md` e promova para a forma mais forte que couber: teste > validação no
  pipeline > regra neste arquivo > ficha.
- Descoberta que muda **como os dados são tratados** (identificação, valores, validação, quebras)
  também é registrada em `docs/METODOLOGIA.md`, com a regra que dela decorre e o A-NNN de origem.
- Toda etapa que muda uma transformação regera `docs/transformacoes/<indice>.html`
  (`python -m macroaf.relatorios.transformacoes --indice <indice>`) no mesmo PR; um teste exige.
  Mudar o formato da explicação não muda os fatos: dúvida continua dúvida (decisão 0004).
- Decisões com alternativas e consequências viram ADR em `docs/decisoes/`.
- As regras ficam em `AGENTS.md` (raiz ou pasta); o `CLAUDE.md` ao lado contém só `@AGENTS.md`.
- Não altere regras deste arquivo, do `CLAUDE.md` nem decisões sem PR revisado pelo mantenedor.
