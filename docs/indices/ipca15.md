# IPCA-15

- **Fonte:** IBGE, SIDRA ([ficha da fonte](../fontes/ibge-sidra.md))
- **Situação no projeto:** piloto (marco *Piloto IPCA-15*)
- **Última conferência dos metadados:** 2026-10-19, na API de agregados (metadados e períodos das
  cinco tabelas) e com amostras da API de valores; resumo no `PLANEJAMENTO.md`, seção 3.1

## O que mede

Variação de preços ao consumidor com a mesma cesta e a mesma metodologia do IPCA, mas com período
de coleta que vai, aproximadamente, da segunda metade do mês anterior à primeira metade do mês de
referência. É divulgado antes do IPCA do mesmo mês.

## Tabelas

| Tabela | Período | Estrutura de pesos | Variáveis |
|---|---|---|---|
| 1646 | mai/2000 → jul/2006 | POF 1995-96 | 355 var. mensal, 356 acum. ano, 357 peso |
| 1387 | ago/2006 → jan/2012 | POF 2002-03 | 355, 356, 357 |
| 1705 | fev/2012 → jan/2020 | POF 2008-09 | 355, 356, 1120 acum. 12 meses (só a partir de mar/2017), 357 |
| 7062 | fev/2020 → atual | POF 2017-18 | 355, 356, 1120 (a partir de jan/2021), 357 |
| 3065 | mai/2000 → atual | — (só índice geral) | 1117 número-índice, 355, 1118 acum. 3m, 1119 acum. 6m, 356, 1120 |

Conferência em 2026-10-19 (`/metadados` e `/periodos`):

| Tabela | `periodicidade.inicio` → `fim` | Períodos | Lacunas | Classificações | Níveis territoriais |
|---|---|---|---|---|---|
| 1646 | 200005 → 200607 | 75 | nenhuma | 315 | N1, N6, N7 |
| 1387 | 200608 → 201201 | 66 | nenhuma | 315 | N1, N6, N7 |
| 1705 | 201202 → 202001 | 96 | nenhuma | 315 | N1, N6, N7 |
| 7062 | 202002 → 202609 | 80 | nenhuma | 315 | N1, N6, N7 |
| 3065 | 200005 → 202609 | 317 | nenhuma | nenhuma | N1 |

Os inícios e fins batem com `config/series.yaml` e as quatro tabelas de dados se sucedem sem lacuna
nem sobreposição. O nome de cada tabela traz o período por extenso (ex.: 1705 "... (de
fevereiro/2012 até janeiro/2020)").

Variáveis (nome e unidade exatamente como nos metadados; batem com o catálogo):

| Id | Nome | Unidade | Tabelas |
|---|---|---|---|
| 355 | IPCA15 - Variação mensal | % | todas |
| 356 | IPCA15 - Variação acumulada no ano | % | todas |
| 357 | IPCA15 - Peso mensal | % | 1646, 1387, 1705, 7062 |
| 1120 | IPCA15 - Variação acumulada em 12 meses | % | 1705, 7062, 3065 |
| 1117 | IPCA15 - Número-índice (base: dezembro de 1993 = 100) | Número-índice | 3065 |
| 1118 | IPCA15 - Variação acumulada em 3 meses | % | 3065 |
| 1119 | IPCA15 - Variação acumulada em 6 meses | % | 3065 |

Datas de troca da estrutura de pesos, conferidas em divulgações do IBGE e do BCB em 2026-10-19:

- **POF 2002-03 a partir de ago/2006.** O IPCA-15 de jul/2006 foi o último com os pesos da POF 1995-96;
  no IPCA a troca foi em jul/2006 ([IBGE, IPCA-15 de julho de 2006](https://agenciadenoticias.ibge.gov.br/agencia-sala-de-imprensa/2013-agencia-de-noticias/releases/13150-asi-ipca-15-de-julho-variou-002);
  [IBGE, IPCA-15 de agosto de 2006](https://agenciadenoticias.ibge.gov.br/agencia-sala-de-imprensa/2013-agencia-de-noticias/releases/13163-asi-ipca-15-de-agosto-variou-019)).
- **POF 2008-09 a partir de fev/2012.** No IPCA a estrutura vigorou de jan/2012 a dez/2019
  ([BCB, Relatório de Inflação dez/2019](https://www.bcb.gov.br/content/ri/relatorioinflacao/201912/ri201912b7p.pdf));
  no IPCA-15 o início em fev/2012 está confirmado pelos metadados oficiais da tabela 1705
  (`periodicidade.inicio = 201202`, primeiro período publicado em 17/02/2012, e nome da tabela
  "de fevereiro/2012 até janeiro/2020"), consultados em 2026-10-19; a 1387 termina em 201201.
- **POF 2017-18 a partir de fev/2020.** As novas estruturas geram "o IPCA e INPC de janeiro, além
  do IPCA-15 de fevereiro" de 2020 ([IBGE, nota técnica 01/2020](https://ftp.ibge.gov.br/Precos_Indices_de_Precos_ao_Consumidor/Sistema_de_Indices_de_Precos_ao_Consumidor/Notas_Tecnicas/snipc_nota_tecnica_2020_01.pdf)).

## Classificação

Classificação 315 "Geral, grupo, subgrupo, item e subitem". Nível derivado pelo código IBGE no
nome da categoria: 1 dígito = grupo, 2 = subgrupo, 4 = item, 7 = subitem.

**Formato do nome**, igual nas quatro tabelas: `<código>.<nome>`, sem espaço depois do ponto
(`1.Alimentação e bebidas`, `11.Alimentação no domicílio`, `1101.Cereais, leguminosas e
oleaginosas`, `1101002.Arroz`). A única categoria sem código é `Índice geral` (id 7169). Os ids das
categorias (7169, 7170, ...) são da API e não coincidem com o código IBGE. Padrão sugerido:
`^(\d+)\.(.+)$`; o que não casar é o geral.

Contagem pelo código IBGE (metadados de 2026-10-19):

| Tabela | Total | Geral | Grupos (1) | Subgrupos (2) | Itens (4) | Subitens (7) |
|---|---|---|---|---|---|---|
| 1646 | 593 | 1 | 9 | 19 | 52 | 512 |
| 1387 | 465 | 1 | 9 | 19 | 52 | 384 |
| 1705 | 446 | 1 | 9 | 19 | 52 | 365 |
| 7062 | 447 | 1 | 9 | 19 | 51 | 367 |

Em todas: nenhum código repetido e nenhum órfão (todo código tem o pai de 1, 2 ou 4 dígitos na
mesma tabela).

Da 1705 para a 7062 some o item `7203.Fotografia e filmagem` (51 itens na 7062); é a única
diferença de itens entre as duas. Está no `map_harmonizacao` (`reference/map_harmonizacao_ipca15.csv`).

O id da categoria na API (`codigo_sidra`) muda quando o IBGE revisa nome ou definição: 87 códigos
IBGE aparecem com ids diferentes entre tabelas, sempre com o nome alterado (ex.: `1101073`
"Feijão - carioca (rajado)" é 7180 na 1646/1387 e 12222 na 1705/7062). O contrário não ocorre:
cada id corresponde sempre ao mesmo código e nome (A-012).

O valor antigo de 1387 ("383 no nível mais detalhado") contava pelo campo `nivel`: um subitem da
1387 vem com `nivel = 0` (ver Peculiaridades) e ficava de fora. Pelo código são 384.

Campo `nivel` por tabela (só para registro; não use):

| Tabela | Geral | Grupo | Subgrupo | Item | Subitem |
|---|---|---|---|---|---|
| 1646 | 0 | 0 | 1 | 2 | 3 |
| 1387 | 0 | 0 | 1 | 2 | 3 (um subitem com 0) |
| 1705, 7062 | 0 | 1 | 2 | 3 | 4 |

## Referência oficial para validação

- **Tabela 3065** (sem classificação; só N1 Brasil): número-índice (1117) e acumulados em 3, 6 e 12 meses (1118, 1119, 1120) do índice
  geral, de mai/2000 em diante. Confere o encadeamento das quatro tabelas e os acumulados calculados.
- **Variáveis 356 e 1120** de cada tabela: conferem os acumulados calculados por categoria, onde
  publicadas (1120 só em 1705 a partir de mar/2017 e em 7062 a partir de jan/2021).

## Peculiaridades

- O campo `nivel` dos metadados muda de escala entre tabelas: em 7062/1705 é 0 = geral, 1 = grupo
  ... 4 = subitem; em 1646/1387 geral **e** grupos têm `nivel = 0` e o subitem é 3 (A-001).
- 2026-10-19: na 1387 o subitem `4103031.Conjunto infantil` (id 12409) vem com `nivel = 0`, como se
  fosse o geral ou um grupo. Tem valores normais (ex.: -0.64 em 200608). Prova concreta de que o
  `nivel` não serve para hierarquia (A-001).
- A classificação é própria do IPCA-15; não reaproveite a do IPCA cheio (A-002).
- 1646 e 1387 não têm acumulado em 12 meses (1120); ele precisa ser calculado e conferido com a 3065
  no índice geral.
- 2026-10-19: a 1705 **declara** a 1120, mas ela vem `...` em todas as 446 categorias de 201202 a
  201702; o primeiro valor numérico é de 201703. Na 7062 a 1120 vem `...` de 202002 a 202012 (os 11
  primeiros meses) e é numérica a partir de 202101. Ou seja, o acumulado em 12 meses por categoria
  precisa ser calculado de abr/2001 (primeiro mês com 12 meses de dados, mai/2000 a abr/2001) até
  fev/2017, atravessando as trocas de POF; no índice geral a 3065 tem a série completa.
- 2026-10-19: nas amostras (1646 v/all 200005-200208; 1387, 1705 e 7062 v/355 todos os períodos)
  toda categoria do metadado tem valor em todo período, inclusive subitens; a 357 (peso) vem com 4
  casas decimais e as variações com 2.
- 1646 (POF 1995-96): **cesta variável** nos itens in natura 1103, 1105 e 1106; pesos de subitem
  sazonais, com 93 zeros, que não reproduzem o item (A-013, `METODOLOGIA.md` 6.2).
- 1646 e 1387: a 356 tem ruído acima do arredondamento (A-016). Erros pontuais publicados em
  1646, 1387, 1705 e 3065 estão listados em `METODOLOGIA.md` 6.4 (A-015).
- Categorias novas na 1387 já vêm com acumulado no ano herdado; na 1705 e na 7062 começam com
  acumulado = variação do mês (A-017).
- Revisão da harmonização (2026-10-20): 116 propostas aceitas e 14 não aceitas (9 casos em
  investigação, issues #32 a #40, o do leite com prioridade); ver `METODOLOGIA.md` 7.4.
- Harmonização (#6): mapa em `reference/map_harmonizacao_ipca15.csv`, série longa em
  `serie_longa_ipca15` no staging. O subgrupo `72` muda de nome duas vezes, o item `1117`
  Alimentos prontos some na 1387 e o `7203` Fotografia e filmagem some na 7062 (A-020). Há
  códigos que somem numa POF e reaparecem na seguinte (ex.: `7189` Amido de milho existe na 1646
  e na 1705, não na 1387): viram `descontinuado` + `novo`, porque há lacuna.
- Índice encadeado (#41): `indice_ipca15` no staging, base 100 por série longa; o geral reproduz o
  número-índice da 3065. No ano da troca de POF, a 356 segue o código (e, em 12 casos da 1387, um
  antecessor escolhido pelo IBGE), não a série longa (A-023, `METODOLOGIA.md` 8.2).
- A troca de POF chega ao IPCA-15 um mês depois de chegar ao IPCA (jul/2006 → ago/2006,
  jan/2012 → fev/2012, jan/2020 → fev/2020). Importa para o IPCA cheio (#12) (A-007).
- Itens e subitens mudam a cada troca de POF; séries longas abaixo de subgrupo dependem de
  `map_harmonizacao` (#6).

## Relação com outros índices

- **IPCA cheio** (#12): mesma classificação 315 e mesmas trocas de POF, mas com mais subitens
  (377 em 7060 contra 367 em 7062) e tabelas próprias. Deve entrar trocando só a configuração.
