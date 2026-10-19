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
- [ ] `docs/METODOLOGIA.md` (fórmula de indicador novo ou alterado), quando existir
- [ ] `data/marts/README.md` (dicionário), quando a etapa mexer nos marts
- [ ] `README.md` (situação do projeto)
- [ ] `CHANGELOG.md`: entrada em "Não publicado"

## 4. Aprendizados

Pergunte: o que foi descoberto nesta etapa que a próxima sessão precisaria saber? Para cada item,
rode `/aprender`. Inclua os aprendizados sugeridos pelo revisor e pelo validador. Se nada foi
aprendido, diga isso no PR.

## 5. PR

- Commits em português.
- Corpo do PR: resumo, `Fecha #N`, resultado de cada passo acima (testes, validações, parecer do
  revisor), aprendizados registrados (A-NNN) e mudanças em regras ou decisões que pedem atenção do
  mantenedor.
