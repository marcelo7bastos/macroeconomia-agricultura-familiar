# Fichas de índices

Uma ficha por índice tratado ou planejado. A ficha concentra o que um agente ou uma pessoa precisa
saber antes de mexer no índice: tabelas, variáveis, estrutura, peculiaridades e referência para
validação. Fichas são criadas e atualizadas pelo subagente `explorador-sidra` (via `/nova-serie`) e
revisadas no PR.

| Índice | Ficha | Situação |
|---|---|---|
| IPCA-15 | [ipca15.md](ipca15.md) | piloto |
| IPCA cheio | [ipca.md](ipca.md) | implementado em revisão [#12](https://github.com/marcelo7bastos/macroeconomia-agricultura-familiar/issues/12) |

## Modelo

```markdown
# <Índice>

- **Fonte:** <instituição> ([ficha da fonte](../fontes/<fonte>.md))
- **Situação no projeto:** piloto | backlog (#N) | em produção
- **Última conferência dos metadados:** AAAA-MM-DD

## O que mede
Uma ou duas frases.

## Tabelas
| Tabela | Período | Estrutura | Variáveis |

## Classificação
Níveis, contagem de categorias por tabela (pelo código IBGE), diferenças entre tabelas.

## Referência oficial para validação
Qual tabela/variável confere o que for calculado.

## Peculiaridades
Lista do que surpreende. Cada item com data e, se houver, a lição (A-NNN).

## Relação com outros índices
O que é igual e o que difere (ex.: IPCA-15 × IPCA).
```
