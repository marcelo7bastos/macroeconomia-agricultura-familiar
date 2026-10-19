# Metodologia

Como os dados do projeto são obtidos, identificados, transformados e validados. Este documento
registra **o método e as descobertas que o justificam**. Cada descoberta tem uma entrada em
[`aprendizados.md`](aprendizados.md) (A-NNN), que conta como ela foi encontrada; aqui fica a regra
que o projeto segue por causa dela.

Escopo atual: piloto **IPCA-15**. Tabelas, períodos e estruturas de pesos estão na ficha
[`indices/ipca15.md`](indices/ipca15.md); decisões de arquitetura, em [`decisoes/`](decisoes/).

## 1. Obtenção dos dados

- Fonte única: APIs oficiais do IBGE (SIDRA e API de agregados). Nenhuma planilha (A-003).
- Extração incremental, um arquivo por tabela × mês, com o corpo exato da resposta; metadados
  também guardados; revisões da fonte guardadas ao lado, sem apagar
  ([decisão 0003](decisoes/0003-extracao-incremental.md), A-008, A-011).
- Antes de baixar, o catálogo (`config/series.yaml`) é conferido com os metadados: período de cada
  tabela e sinal de troca de tabela (#27).

## 2. Identificação das categorias

Cada categoria da classificação 315 (geral, grupo, subgrupo, item, subitem) tem **dois
identificadores**, e eles não são intercambiáveis:

| Identificador | Exemplo | Onde aparece | O que identifica |
|---|---|---|---|
| **Código IBGE** (`codigo_ibge`) | `1101073` | no nome da categoria: `1101073.Feijão - carioca (rajado)` | a **posição** na hierarquia: `1` grupo → `11` subgrupo → `1101` item → `1101073` subitem |
| **Id SIDRA** (`codigo_sidra`) | `12222` | campo `id` da categoria nos metadados; `D4C` nos valores | a **definição** da categoria numa versão da classificação |

### 2.1 O que descobrimos (A-012)

Comparando as quatro tabelas do IPCA-15, o mesmo código IBGE aparece com ids SIDRA diferentes
em 87 casos (84 subitens, 2 itens, 1 subgrupo). Em **todos** eles o nome também mudou. O
contrário nunca acontece: um id SIDRA corresponde sempre ao mesmo código e ao mesmo nome. Ou seja,
o IBGE cria um id novo quando revisa a categoria e mantém o código da posição na árvore.

| Troca de POF | Códigos nas duas tabelas | Com id novo (e nome novo) | Só na anterior | Só na nova |
|---|---|---|---|---|
| 1646 → 1387 (ago/2006) | 421 | 37 | 172 | 44 |
| 1387 → 1705 (fev/2012) | 415 | 30 | 50 | 31 |
| 1705 → 7062 (fev/2020) | 388 | 13 | 58 | 59 |

As mudanças com id novo são de naturezas diferentes:

| Natureza | Exemplos (código: antes → depois) |
|---|---|
| Só grafia | `1101073`: "Feijão - carioca (rajado))" → "Feijão - carioca (rajado)" (id 7180 → 12222); `1101053`: "macassar" → "macáçar" |
| Mesmo conceito, nome atualizado | `3202028`: Microcomputador → Computador pessoal; `7201090`: Hotel → Hospedagem; `1110009`: Frango → Frango inteiro |
| **Escopo ampliado** | `1114083`: Refrigerante → Refrigerante e água mineral; `1111019`: Iogurte → Iogurte e bebidas lácteas; `1114029`: Mate → Chá |
| **Produto diferente** | `1111004`: Leite pasteurizado → Leite longa vida |

### 2.2 Regras que seguem disso

1. **Valores são ligados à classificação por `(tabela_sidra, codigo_sidra)`.** É a única chave
   que identifica sem ambiguidade a categoria de um valor. O código IBGE sozinho não serve, porque
   o mesmo código pode ser categorias diferentes em tabelas diferentes. O contrato da
   `dim_classificacao` garante id único por tabela, e um teste garante que cada id tem sempre o
   mesmo código e nome.
2. **Código IBGE igual não autoriza emendar séries entre POFs.** Para montar a série longa de um
   item ou subitem, cada par de categorias de POFs consecutivas é classificado no
   `map_harmonizacao` (#6): `identico`, `renomeado`, `dividido`, `fundido`, `descontinuado`, `novo`.
   - Mesmo código e mesmo id: candidato a `identico`.
   - Mesmo código e id novo: **revisão manual obrigatória**. Grafia ou nome atualizado podem virar
     `renomeado` (série contínua); escopo ampliado ou produto diferente são **quebra de série**
     (marcada, nunca escondida).
   - Código que some ou aparece: `descontinuado` ou `novo`, salvo se a revisão encontrar a
     correspondência em outro código (ex.: item `7203` Fotografia e filmagem, que some na 7062).
3. Até o **subgrupo**, a estrutura é estável entre POFs e as séries longas são publicadas sem
   harmonização (seção 4.3 do planejamento).

## 3. Hierarquia

- O nível vem do número de dígitos do código IBGE (1, 2, 4, 7). O campo `nivel` dos metadados
  **não é usado**: muda de escala entre tabelas e marca um subitem da 1387 com `nivel = 0`
  (A-001, A-010).
- O índice geral não tem código; recebe `0` por convenção do projeto.
- A classificação vem dos metadados de cada tabela: o IPCA-15 tem classificação própria, diferente
  da do IPCA cheio (A-002).

## 4. Valores

- O SIDRA devolve texto com ponto decimal: 2 casas nas variações, 4 no peso.
- `...` (dado não disponível) vira **ausente**, nunca zero. Qualquer outro texto não numérico
  interrompe a transformação até ganhar um tratamento documentado aqui (A-009).
- A API devolve só 2 casas nas variações, mesmo pedindo mais (`/d/m`); não há precisão maior.
- A variável 1120 (acumulado em 12 meses) consta nos metadados, mas vem `...` em 2012-02 a
  2017-02 (1705) e 2020-02 a 2020-12 (7062), e não existe na 1646 nem na 1387 (A-009). Nesses
  meses o acumulado em 12 meses é calculado (seção 6) e conferido com a 3065 no índice geral.

## 5. Tabelas de staging

Geradas por `uv run python -m macroaf.transform.ipca15` a partir do raw, sem rede. Colunas e
semântica na seção 4.2 do [planejamento](PLANEJAMENTO.md).

- `dim_classificacao`: uma linha por categoria e tabela.
- `fato_ipca15`: uma linha por mês e categoria; variáveis em colunas. Ligado à classificação por
  `(tabela_sidra, codigo_sidra)` (seção 2.2).
- `ref_ipca15_geral`: tabela 3065 (número-índice e acumulados do índice geral).

## 6. Validações

Rodam com `uv run python -m macroaf.validate.ipca15` (grava `validacao.json` no staging) e em
todo PR pelo `pytest`. Qualquer falha bloqueia a publicação.

### 6.1 Limite de arredondamento, não tolerância arbitrária (A-014)

O SIDRA publica variações com 2 casas (erro de até ±0,005) e pesos com 4 casas (±0,00005). Cada
validação compara a diferença com **o maior erro que esse arredondamento pode produzir** naquele
caso. Abaixo do limite é arredondamento; acima é anomalia, que precisa de explicação.

| # | Validação | Regra | Limite |
|---|---|---|---|
| 1 | `esquema` | tipos, chaves únicas, peso entre 0 e 100, variação plausível | subitem entre -100% e +300%; demais níveis entre -50% e +50% |
| 2 | `pesos_grupos` | os 9 grupos somam 100 em cada mês | 0,00005 × (grupos + 1) |
| 2 | `pesos_filhos` | os filhos somam o peso do pai | 0,00005 × (filhos + 1) |
| 2 | `pesos_zero` | nenhum peso igual a zero | — |
| 3 | `reconciliacao` | média dos filhos ponderada pelo peso do mês = variação do pai | 0,005 + 0,005 + Σ 0,00005·\|v_i − v\| / Σw |
| 4 | `continuidade` | toda categoria tem valor em todos os meses da sua tabela | — |
| 5 | `acumulado_ano` | `A_t = (1+A_{t−1})(1+v_t) − 1` (janeiro: `A = v`), um passo por vez | 0,005(1+\|A_{t−1}\|) + 0,005(1+\|v_t\|) + 0,005; na 1646/1387, o maior entre isso e o limite por nível (6.3) |
| 5 | `acumulado_12m` | composição das 12 variações mensais = 1120, onde publicada | 0,005(1+\|A\|)·Σ 1/(1+v_i) + 0,005 |
| 6 | `costura_mensal` | variação do geral das 4 tabelas = 355 da 3065 | igualdade exata |
| 6 | `costura_acumulados` | 3, 6, 12 meses e ano do geral = 1118, 1119, 1120 e 356 da 3065 | 0,01 (3, 6, ano); 0,02 (12) |
| 6 | `costura_numero_indice` | `I_t = I_{t−1}(1+v_t)` contra a 1117 | 0,00005·I + 0,01 por passo |
| 6 | `costura_numero_indice_encadeado` | índice encadeado desde mai/2000 contra a 1117 | desvio relativo de 0,01% |

O acumulado no ano é validado **um passo por vez**: assim um erro da fonte num mês não contamina
os seguintes. Meses sem o mês anterior na mesma tabela (início de tabela fora de janeiro) não são
validados nessa regra; o índice geral desses meses é coberto pela costura com a 3065.

### 6.2 Cesta variável nos in natura da POF 1995-96 (A-013)

Na tabela 1646 (mai/2000 a jul/2006), os itens **1103 Tubérculos, raízes e legumes**,
**1105 Hortaliças e verduras** e **1106 Frutas** não são a média ponderada dos seus subitens
(diferença de até 6,6 p.p.). Os dados mostram uma cesta variável (sazonal): os pesos dos subitens
seguem o calendário de safra (correlação de 0,999 entre o mesmo mês de anos seguidos), há 93
pesos iguais a zero (subitem fora de safra) e o acumulado no ano dos subitens não fecha com as
variações mensais. O nível do item é coerente: o subgrupo 11 reconcilia pelos itens. Na 1387 em
diante o fenômeno some.

Consequências:

- Na 1646, esses três itens são validados pelo nível acima (subgrupo 11), não pelos subitens; o
  acumulado no ano dos subitens e os pesos zero são aceitos como **exceção estrutural**.
- **Contribuição de subitem** (indicador da #7) não soma ao item nesses três itens da 1646; ali a
  contribuição é calculada a partir do item.
- A documentação do IBGE sobre a cesta variável não pôde ser consultada nesta sessão (domínios
  bloqueados); a conclusão se apoia nos dados. Referência a confirmar: Série Relatórios
  Metodológicos do SNIPC e notas técnicas da atualização de 2006.

### 6.3 Ruído da fonte no acumulado no ano das tabelas antigas (A-016)

Na 1705 e na 7062 a variável 356 fecha com as variações mensais dentro do limite de
arredondamento. Na 1646 e na 1387 não: o ruído é maior que o arredondamento (até 0,02 no geral,
que também diverge da 356 da 3065). É procedimento da fonte, não erro nosso. Por isso, nessas
duas tabelas, o limite é o máximo observado por nível na calibração (geral 0,02; grupo 0,02;
subgrupo 0,03; item 0,07; subitem 0,17). Para o índice geral, a referência é a 3065.

### 6.4 Erros publicados pela fonte (A-015)

Conferidos na API, explicados e mantidos como publicados (o projeto não corrige dado oficial):

| Tabela | Mês | Onde | O que está errado |
|---|---|---|---|
| 1646 | 2003-02 | 356 de todas as categorias menos o geral | valores trocados (grupo 1: publica 1,55; pela 355 dá 4,25) |
| 1646 | 2004-07 | 356 de todas as categorias menos o geral | repete o valor de 2004-08 |
| 1387 | 2010-07 e 08 | pesos | toda a árvore multiplicada por 1,000999 (grupos somam 100,1) |
| 1387 | 2011-10 e 11 | item 1115 Enlatados e conservas | item incoerente com os subitens; palmito com saltos de peso sem variação |
| 1705 | 2014-07 e 09 | item 9101 Comunicação | subitem 9101022 publica 0,00, mas o peso implica cerca de -1,3% |
| 3065 | 2006-04, 2011-11, 2012-11 | acumulados 1118/1119 do geral | contradizem o número-índice da própria tabela (ex.: 6 meses em abr/2006: 0,54 publicado, 2,76 pelo índice) |

### 6.5 Exceções

Ficam em [`reference/excecoes_validacao_ipca15.csv`](../reference/excecoes_validacao_ipca15.csv):
validação, tabela, padrão do código IBGE (expressão regular), faixa de meses, tipo (`estrutural`
ou `fonte`), justificativa e A-NNN. Regras:

- Exceção sem justificativa, tipo ou aprendizado é rejeitada.
- **Toda exceção precisa continuar cobrindo uma falha.** Se o IBGE corrigir o dado, a exceção
  deixa de ser usada, o teste avisa e ela é removida.
- Nada é ignorado em silêncio: o relatório mostra quantas diferenças cada exceção cobriu.

## 7. Registro de descobertas

Toda descoberta sobre os dados ou o método segue o ciclo de [`aprendizados.md`](aprendizados.md):
entra como A-NNN, é promovida para teste ou validação quando possível e, se muda o método, é
registrada neste documento com a regra que dela decorre.
