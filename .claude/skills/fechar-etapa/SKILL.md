---
name: fechar-etapa
description: Checklist para concluir uma issue e abrir o PR - testes, ruff, validações de dados, revisão metodológica, documentação, CHANGELOG e aprendizados. Use antes de abrir qualquer PR ou quando o usuário pedir /fechar-etapa.
---

# /fechar-etapa

Rode os passos em ordem. Se um passo falhar, corrija antes de seguir; não abra PR com pendência
sem declará-la.

## 1. Código

- `uv run ruff check .` e `uv run ruff format --check .`
- `uv run pytest`
- Se a etapa produz dados: rode as validações. Se alguma falhar, acione o subagente
  `validador-dados` e trate o diagnóstico.

(Enquanto não existir `pyproject.toml`, registre "sem código ainda" e siga.)

## 2. Revisão metodológica

Acione o subagente `revisor-metodologico` sobre `git diff origin/main...HEAD`. Bloqueios precisam ser
corrigidos; ressalvas vão para o PR (corrigidas ou justificadas).

## 3. Documentação

Confira e atualize o que a mudança tocar:

- [ ] `docs/PLANEJAMENTO.md` (escopo, roteiro, seção 9 de decisões)
- [ ] `docs/decisoes/` (ADR nova se houve escolha entre alternativas)
- [ ] `docs/indices/` e `docs/fontes/` (fichas)
- [ ] `docs/METODOLOGIA.md`: fórmula de indicador novo ou alterado e toda descoberta que mude o
      tratamento dos dados (com o A-NNN de origem)
- [ ] `data/marts/README.md` (dicionário): sai do `DICIONARIO` em `macroaf.marts.publicar`; ao
      mexer nos marts, atualize lá
- [ ] `README.md` (situação do projeto)
- [ ] `docs/transformacoes/<indice>.html`: regerar com
      `uv run python -m macroaf.relatorios.transformacoes --indice <indice>` e revisar o que mudou
      (resumo, dúvidas em aberto, o que existe); se uma dúvida foi resolvida ou surgiu, atualizar
      `DUVIDAS` no gerador
- [ ] `data/marts/`: republicar com `uv run python -m macroaf.marts.publicar --indice <indice>`
      quando o pipeline ou os dados mudam (um teste exige os marts em dia)
- [ ] `CHANGELOG.md`: entrada em "Não publicado"

## 4. Aprendizados

Pergunte: o que foi descoberto nesta etapa que a próxima sessão precisaria saber? Para cada item,
rode `/aprender`. Inclua os aprendizados sugeridos pelo revisor e pelo validador. Se nada foi
aprendido, diga isso no PR.

## 5. PR

- Commits em português.
- Corpo do PR: resumo, `Closes #N (fecha #N)` (A-027; em PR empilhado, fechar a issue à mão
  depois do merge), resultado de cada passo acima (testes, validações, parecer do
  revisor), aprendizados registrados (A-NNN) e mudanças em regras ou decisões que pedem atenção do
  mantenedor.
