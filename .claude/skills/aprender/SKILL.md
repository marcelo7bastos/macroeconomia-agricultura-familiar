---
name: aprender
description: Registra uma lição aprendida em docs/aprendizados.md e a promove para a forma mais forte possível (teste, validação, regra no CLAUDE.md ou ficha). Use ao descobrir algo não óbvio sobre os dados, as APIs, o método ou o próprio fluxo de trabalho, ou quando o usuário pedir /aprender.
---

# /aprender

Transforma uma descoberta em conhecimento durável do projeto. A memória dos agentes é o repositório:
o que não estiver no git se perde quando a sessão termina.

## Quando registrar

- Um erro custou tempo e pode se repetir.
- A API ou os dados se comportam de um jeito não documentado.
- Uma decisão de método foi tomada (se tiver alternativas e consequências, faça também uma ADR).
- Uma regra existente se mostrou errada ou incompleta.

Não registre o óbvio nem o que já está em `CLAUDE.md`, no planejamento ou nas fichas.

## Passos

1. Leia `docs/aprendizados.md` e confira se a lição já existe. Se existir, atualize a entrada em vez
   de duplicar.
2. Escolha o destino, do mais forte para o mais fraco:
   1. **Teste automatizado** (`tests/`): quando dá para verificar no código. Um bug vira teste de
      regressão.
   2. **Validação no pipeline** (`src/macroaf/validate/`): quando é propriedade dos dados.
   3. **Regra no `CLAUDE.md`** (raiz ou de uma pasta): quando é conduta que vale em toda sessão.
      Mantenha o arquivo curto; uma regra nova pode substituir outra.
   4. **Ficha** (`docs/indices/`, `docs/fontes/`): quando é conhecimento sobre um índice ou fonte.
3. Faça a promoção no mesmo branch, se couber no escopo da issue. Se não couber, abra uma issue e
   anote o número na entrada.
4. Adicione a entrada **no topo** da seção "Registro" de `docs/aprendizados.md`, com o próximo número:

   ```markdown
   ### A-NNN · AAAA-MM-DD · título curto
   - **Contexto:** o que estava sendo feito (issue/PR).
   - **O que aconteceu:** fato observado, com evidência.
   - **Lição:** o que fazer (ou evitar) daqui em diante.
   - **Promovida para:** `tests/...` | validação `...` | `CLAUDE.md` | ficha `...` | issue #N | nenhuma (motivo).
   ```

5. Mudanças no `CLAUDE.md` ou em decisões vão no PR para revisão do mantenedor; avise no corpo do PR.
