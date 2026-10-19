# IPCA-15

- **Fonte:** IBGE, SIDRA ([ficha da fonte](../fontes/ibge-sidra.md))
- **Situação no projeto:** piloto (marco *Piloto IPCA-15*)
- **Última conferência dos metadados:** 2026-10-19 (registrada no `PLANEJAMENTO.md`, seção 3.1)

## O que mede

Variação de preços ao consumidor com a mesma cesta e a mesma metodologia do IPCA, mas com período
de coleta que vai, aproximadamente, da segunda metade do mês anterior à primeira metade do mês de
referência. É divulgado antes do IPCA do mesmo mês.

## Tabelas

| Tabela | Período | Estrutura de pesos | Variáveis |
|---|---|---|---|
| 1646 | mai/2000 → jul/2006 | POF 1995-96 | 355 var. mensal, 356 acum. ano, 357 peso |
| 1387 | ago/2006 → jan/2012 | POF 2002-03 | 355, 356, 357 |
| 1705 | fev/2012 → jan/2020 | POF 2008-09 | 355, 356, 1120 acum. 12 meses, 357 |
| 7062 | fev/2020 → atual | POF 2017-18 | 355, 356, 1120, 357 |
| 3065 | mai/2000 → atual | — (só índice geral) | 1117 número-índice, 355, 1118 acum. 3m, 1119 acum. 6m, 356, 1120 |

## Classificação

Classificação 315 (geral, grupo, subgrupo, item, subitem). Nível derivado pelo código IBGE no nome
da categoria: 1 dígito = grupo, 2 = subgrupo, 4 = item, 7 = subitem.

| Tabela | Categorias |
|---|---|
| 7062 | 1 geral, 9 grupos, 19 subgrupos, 51 itens, 367 subitens |
| 1705 | 1 geral, 9 grupos, 19 subgrupos, 52 itens, 365 subitens |
| 1387 | 383 no nível mais detalhado |
| 1646 | 512 no nível mais detalhado |

A contagem de 1387 e 1646 ainda precisa ser refeita pelo código IBGE (#4).

## Referência oficial para validação

- **Tabela 3065:** número-índice (1117) e acumulados em 3, 6 e 12 meses (1118, 1119, 1120) do índice
  geral, de mai/2000 em diante. Confere o encadeamento das quatro tabelas e os acumulados calculados.
- **Variáveis 356 e 1120** de cada tabela: conferem os acumulados calculados por categoria.

## Peculiaridades

- O campo `nivel` dos metadados muda de escala entre tabelas: 7062/1705 começam em 0 = geral,
  1646/1387 usam outra numeração (A-001).
- A classificação é própria do IPCA-15; não reaproveite a do IPCA cheio (A-002).
- 1646 e 1387 não têm acumulado em 12 meses (1120); ele precisa ser calculado e conferido com a 3065
  no índice geral.
- Itens e subitens mudam a cada troca de POF; séries longas abaixo de subgrupo dependem de
  `map_harmonizacao` (#6).

## Relação com outros índices

- **IPCA cheio** (#12): mesma classificação 315 e mesmas trocas de POF, mas com mais subitens
  (377 em 7060 contra 367 em 7062) e tabelas próprias. Deve entrar trocando só a configuração.
