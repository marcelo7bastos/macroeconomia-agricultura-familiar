# 0002. Agentes por função, não por índice

- **Situação:** aceita
- **Data:** 2026-10-19
- **Issue/PR:** #20

## Contexto

O projeto vai tratar vários índices e fontes (IPCA-15, IPCA, PIB, Selic, Pronaf...). Uma opção era
um agente orquestrador com um agente especialista por índice. O planejamento exige que o que for
construído para o IPCA-15 sirva para o IPCA cheio "trocando apenas a configuração".

## Decisão

- O **orquestrador é a sessão principal** do Claude Code: lê o roteiro e as issues, aciona
  subagentes e abre o PR.
- **Subagentes por função** (`.claude/agents/`): `revisor-metodologico` (só leitura),
  `validador-dados` (executa, não edita) e `explorador-sidra` (documenta fontes).
- **Skills** para procedimentos repetíveis (`.claude/skills/`): `/nova-serie`, `/fechar-etapa`,
  `/aprender`.
- A **especialização por índice** fica em configuração (`config/series.yaml`) e em fichas
  (`docs/indices/`), que todos os agentes leem.

## Alternativas consideradas

- **Orquestrador + um agente por índice:** duplicaria o mesmo conhecimento (extração, hierarquia,
  harmonização, validação) em cada agente; uma lição aprendida num índice teria de ser copiada para
  os outros, e as cópias divergiriam.
- **Orquestrador como agente separado:** acrescentaria uma camada sem ganho; a sessão principal já
  cumpre esse papel.

## Consequências

- Uma lição vale para todos os índices de uma vez.
- Incluir um índice é um roteiro (`/nova-serie`), não um agente novo.
- Criar um subagente novo só quando surgir uma função recorrente que os atuais não cobrem (ex.:
  revisão de harmonização na #6). Reavaliar se índices com métodos muito diferentes (Contas
  Nacionais, crédito rural) passarem a ser desenvolvidos em paralelo.
