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
   - Mesmo código e id novo: **revisão manual obrigatória**, inclusive quando só a grafia muda.
     Grafia ou nome atualizado podem virar `renomeado` (série contínua); escopo ampliado ou
     produto diferente são **quebra de série** (marcada, nunca escondida). Ver seção 7.
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
  2017-02 (1705) e 2020-02 a 2020-12 (7062), e não existe na 1646 nem na 1387 (A-009). No
  `fato_ipca15` esses meses ficam **ausentes**. O acumulado em 12 meses por categoria nesses
  meses será calculado nos indicadores (#7); hoje só o do índice geral é calculado, na validação,
  e conferido com a 3065.

## 5. Tabelas de staging

Geradas por `uv run python -m macroaf.transform.ipca15` a partir do raw, sem rede. Colunas e
semântica na seção 4.2 do [planejamento](PLANEJAMENTO.md).

- `dim_classificacao`: uma linha por categoria e tabela.
- `fato_ipca15`: uma linha por mês e categoria; variáveis em colunas. Ligado à classificação por
  `(tabela_sidra, codigo_sidra)` (seção 2.2).
- `ref_ipca15_geral`: tabela 3065 (número-índice e acumulados do índice geral).

## 6. Validações

Rodam com `uv run python -m macroaf.validate.ipca15` (grava `validacao.json` no staging) e em
todo PR pelo `pytest`. Qualquer falha bloqueia a publicação, e também qualquer exceção cuja
contagem mude (6.5). Uma diferença que não pode ser calculada (ex.: pai ausente) conta como falha,
salvo onde a regra não se aplica (acumulado em 12 meses não publicado, janela incompleta).

O que varia por índice fica fora do código: tabelas e períodos no catálogo
(`config/series.yaml`), exceções em `reference/excecoes_validacao_<indice>.csv` e limites
empíricos em `reference/limites_validacao_<indice>.csv`.

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
| 4 | `continuidade` | toda categoria da `dim_classificacao` tem valor em todos os meses que o catálogo espera para a tabela, e só neles | — |
| 5 | `acumulado_ano` | janeiro: `A = v`; demais meses: `A_t = (1+A_{t−1})(1+v_t) − 1`, um passo por vez | janeiro: **igualdade exata** (vale em todas as 12.598 linhas); demais: 0,005(1+\|A_{t−1}\|) + 0,005(1+\|v_t\|) + 0,005, ou o limite por nível da 1646/1387 (6.3) |
| 5 | `acumulado_12m` | composição das 12 variações mensais = 1120, onde publicada | 0,005(1+\|A\|)·Σ 1/(1+v_i) + 0,005 |
| 6 | `costura_mensal` | variação do geral das 4 tabelas = 355 da 3065 | igualdade exata |
| 6 | `costura_acum_3m`, `_6m`, `_12m`, `_ano` | composição da variação mensal do geral = 1118, 1119, 1120 e 356 da 3065, cada variável validada à parte | 0,005(1+\|A\|)·Σ 1/(1+v_i) + 0,005 |
| 6 | `costura_numero_indice` | `I_t = I_{t−1}(1+v_t)` contra a 1117 | 0,00005·I + 0,01 por passo |
| 6 | `costura_numero_indice_encadeado` | índice encadeado desde mai/2000 contra a 1117 | desvio relativo de 0,01% (empírico; máximo observado 0,003%) |

Maior razão diferença/limite observada fora das exceções: 0,98 (acumulado no ano), 0,97
(reconciliação), 0,83 (costura), 0,80 (pesos), 0,73 (12 meses).

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
- **Limite desta validação:** os subitens desses três itens na 1646 não têm nenhuma identidade
  que confira a variação mensal; um erro neles só é pego pela faixa plausível do esquema.
- A documentação do IBGE sobre a cesta variável não pôde ser consultada nesta sessão (domínios
  bloqueados); a conclusão se apoia nos dados. Referência a confirmar: Série Relatórios
  Metodológicos do SNIPC e notas técnicas da atualização de 2006.

### 6.3 Ruído da fonte no acumulado no ano das tabelas antigas (A-016)

Na 1705 e na 7062 a variável 356 fecha com as variações mensais dentro do limite de
arredondamento. Na 1646 e na 1387 não: o ruído é maior que o arredondamento (até 0,02 no geral,
que também diverge da 356 da 3065). É procedimento da fonte, não erro nosso. Por isso, nessas
duas tabelas, o limite é **empírico**: o percentil 99,9 da diferença por nível na calibração,
em `reference/limites_validacao_ipca15.csv` (1646: subgrupo 0,019, item 0,035, subitem 0,065;
1387: item 0,033, subitem 0,062; os demais níveis ficam no limite analítico). Os poucos casos
acima do p99,9 (1646: 33; 1387: 25) não ampliam o limite: entram como exceções **contadas**, de
modo que um erro novo, mesmo pequeno, muda a contagem e é detectado. Para o índice geral, a
referência é a 3065.

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
validação (uma variável por linha), tabela, padrão do código IBGE (expressão regular), faixa de
meses, tipo (`estrutural` ou `fonte`), justificativa, A-NNN e **número exato de falhas que
cobre**. Regras (A-018):

- O escopo da exceção é o da justificativa: se o erro está na 1119, a exceção é da
  `costura_acum_6m`, e a 1118, a 1120 e a 356 do mesmo mês continuam validadas.
- Exceção sem justificativa, tipo, aprendizado ou contagem é rejeitada.
- **Sentinela por contagem exata.** Cada falha é atribuída à primeira exceção que a cobre (na
  ordem do arquivo), e a contagem precisa ser igual à registrada. Menos: o IBGE pode ter corrigido
  o dado; mais: há erro novo no escopo. Nos dois casos a validação falha até a exceção ser revista.
- As exceções de 2003-03 e 2004-08 na 1646 existem só porque a validação de um passo usa o mês
  anterior (errado na fonte) como âncora.
- **Mês com erro publicado.** A coluna `meses_com_erro_publicado` separa o mês em que o valor
  publicado está errado (ex.: 2003-02) dos meses que a exceção cobre só por consequência (2003-03).
  Só ela autoriza os indicadores a trocar o oficial pelo calculado (seção 9).

## 7. Harmonização entre POFs e série longa

Gerada por `uv run python -m macroaf.transform.harmonizacao`, que atualiza
[`reference/map_harmonizacao_ipca15.csv`](../reference/map_harmonizacao_ipca15.csv) (preservando o
que foi revisado) e grava `serie_longa_ipca15` no staging. Decisão
[0005](decisoes/0005-na-duvida-quebra.md).

### 7.1 Na dúvida, quebra

Cada categoria de uma tabela é ligada à da tabela seguinte com um tipo: `identico`, `renomeado`,
`fundido`, `dividido`, `descontinuado` ou `novo`. Só `identico` e `renomeado` emendam a série, e
só quando a ligação é **automática** (com prova: o mesmo id SIDRA) ou **revisada** por uma pessoa.
Proposta não revisada ou **rejeitada** conta como quebra. Encerrar uma série nunca esconde nada;
emendar errado esconde.

| Situação | Quando | Exemplo |
|---|---|---|
| `identico`, automático | mesmo código IBGE e mesmo id SIDRA (o id identifica a definição, A-012) | `1101002` Arroz em todas as tabelas |
| `renomeado`, proposto | mesmo código, id novo (mesmo que só a grafia mude: o id novo é definição nova, A-012) | `1101073` "(rajado))" → "(rajado)"; `1111004` Leite pasteurizado → Leite longa vida |
| `fundido` ou `dividido`, proposto | nomes aparentados no mesmo item, incluindo categorias que mantêm o código com id novo (A-021); entre itens diferentes, só código extinto → código novo com todas as palavras do nome menor no maior | Refrigerante + Água mineral → Refrigerante e água mineral; peixes regionais → `1108006` Peixe; `8102005` Livro → didático e não didático |
| `descontinuado` ou `novo`, automático | código some ou aparece e nenhum candidato pelas regras | `1101079` Milho em grão (só na 1646) |

O parentesco de nomes conta as palavras do nome menor que aparecem no maior, sem as palavras
vazias ("de", "e", "para") e com o plural simples reduzido ("lentes" → "lente"), e exige mais da
metade das palavras do maior ou todas as do menor. Uma palavra genérica em comum ("Peixe -
cavalinha" e "Peixe - linguado") não basta (A-019).

**Como a revisão acontece.** As propostas são revisadas na página
`docs/revisao/harmonizacao_ipca15.html` (gerada por `python -m macroaf.relatorios.revisao`),
agrupadas: ligações que tocam as mesmas categorias aparecem no mesmo cartão e são revisadas
juntas. Aceitar grava `situacao = revisado`; não aceitar grava `situacao = rejeitado` com a
observação. As decisões são aplicadas ao mapa com
`python -m macroaf.transform.harmonizacao --decisoes <json> --revisor <nome>` e preservadas
quando o mapa é regerado. Uma ligação que as regras não viram pode ser acrescentada à mão como
`revisado`; ela substitui o `descontinuado`/`novo` automático das categorias que liga. O mapa é
conferido a cada execução: toda decisão tem revisor, aponta para categorias que existem com o
mesmo código e nome, e liga tabelas consecutivas.

### 7.2 Série longa

`serie_longa_ipca15` tem as linhas do fato com: `serie_id` (código IBGE e POF da primeira
categoria da série, estável quando entra POF nova), `inicio_serie`, `fim_serie`, `entrada` e
`saida` (início ou fim dos dados, `novo`, `descontinuado`, o tipo que interrompeu a série,
"proposta não revisada" ou "proposta rejeitada"). Invariantes conferidos a cada execução: cada
linha do fato aparece uma vez, uma série tem um valor por mês e sem lacuna, e não muda de nível
hierárquico.

O `serie_id` não muda quando entra uma POF nova, mas **muda com a revisão**: aceitar a emenda de
duas séries faz a segunda desaparecer dentro da primeira. Por isso o `serie_id` não é chave de
mart; os marts (#8) precisam de uma chave própria e estável.

### 7.3 Nem os subgrupos são totalmente estáveis (A-020)

Grupos são idênticos em todas as trocas. Mas o subgrupo `72` muda duas vezes ("Recreação, fumo e
filmes" → "Recreação, fumo e fotografia" → "Recreação e fumo"), o item `7203` Fotografia e
filmagem some na 7062 e o item `1117` Alimentos prontos some na 1387. Por isso subgrupos e itens
passam pela mesma regra dos subitens, e a afirmação "até subgrupo a série sai direto" (seção 4.3 do
planejamento) vale só depois da revisão desses casos.

### 7.4 Resultado da revisão (#6)

Revisão feita pelo mantenedor (marcelo7bastos) em 2026-10-20, na página de revisão: as 130
propostas foram decididas, **116 aceitas e 14 não aceitas**. Cada decisão está no mapa com
`situacao` (`revisado` ou `rejeitado`), revisor e observação.

| Efeito | Antes da revisão | Depois |
|---|---|---|
| Séries longas | 807 | 731 |
| Subitens contínuos de mai/2000 a set/2026 | 212 | 261 |
| Itens contínuos de mai/2000 a set/2026 | 48 | 50 |

As 14 ligações não aceitas formam 9 casos, todos quebra marcada até a investigação:

| Caso | Issue |
|---|---|
| Leite pasteurizado → Leite longa vida (prioridade) | #32 |
| Massa para pão de queijo → Queijo | #33 |
| Subgrupo 72: Recreação, fumo e fotografia → Recreação e fumo | #34 |
| Peixe dividido em espécies (4 ligações) | #35 |
| Conserto de aparelho de som → Conserto de aparelho celular | #36 |
| Óculos sem grau → Óculos de grau | #37 |
| Livro → didático e não didático (2 ligações) | #38 |
| Telefone celular → Plano de telefonia móvel | #39 |
| TV por assinatura com internet → TV por assinatura e Combo (2 ligações) | #40 |

**Divisões e comparação retroativa (A-022).** Na observação sobre o peixe, o mantenedor registrou
que, quando uma categoria vira várias, ainda é possível comparar com o passado somando as novas
no nível da antiga, mas não seguir a série antiga para o presente e o futuro. Por isso uma divisão
não aceita não é emendada; a comparação retroativa agregada é tema das issues #35, #38 e #40.

## 8. Índice encadeado (#41)

O índice encadeado é a base dos acumulados por janela (#42) e das contribuições acumuladas (#43).
É calculado em `indice_ipca15` (`macroaf.indicators.indice`) para cada `serie_id` da série longa,
a partir da variação mensal oficial (variável 355):

    I_t = I_(t-1) × (1 + v_t / 100),   com I = 100 no mês anterior ao início da série

- **Cada série começa em 100.** O índice nunca atravessa uma quebra da harmonização (decisão 0005):
  série nova, índice novo. Comparar níveis de séries diferentes não faz sentido; comparar
  variações, sim.
- **Uma base só.** O acumulado de k meses é `(I_t / I_(t-k) − 1) × 100`, e a primeira janela
  completa usa a base 100. Mudar a base para um mês escolhido é uma divisão (`rebasear`); não se
  guardam várias bases.
- **Sem lacuna.** Mês faltando, mês repetido ou variação ausente param a transformação, porque o
  encadeamento e as janelas por deslocamento supõem séries contínuas.
- **Cesta variável marcada.** As linhas cobertas pela exceção estrutural de `acumulado_ano` da 1646
  (subitens in natura da POF 1995-96, A-013) recebem `cesta_variavel = True`: o índice é calculável,
  mas os acumulados cuja janela inclui esses meses não reproduzem os do IBGE (8.3).

### 8.1 Conferência contra o IBGE

| O que | Referência | Resultado |
|---|---|---|
| Índice do geral | número-índice (1117) da 3065 | desvio relativo máximo de 0,003% (teste exige ≤ 0,01%) |
| Acumulados em 3, 6 e 12 meses do geral | 1118, 1119 e 1120 da 3065 | dentro do limite de arredondamento (A-014), salvo os 4 erros publicados já conhecidos (A-015) |
| Acumulado no ano do geral | 356 da 3065 | dentro do limite em todos os meses |
| Acumulado em 12 meses por categoria | 1120 | dentro do limite em todas as linhas publicadas |
| Acumulado no ano por categoria, dentro de uma tabela | 356 da 1705 e da 7062 | dentro do limite em todas as linhas (na 1646 e na 1387 o ruído da fonte é tratado na validação, A-016) |

O limite é o mesmo das validações: o índice é composto de variações com 2 casas, e o erro máximo
de um acumulado de k meses é `0,005 × (1 + A/100) × Σ 1/(1 + v_j/100) + 0,005`.

### 8.2 Acumulado no ano no ano da troca de POF (A-023)

A 356 publicada no ano em que entra uma tabela nova revela a âncora que o **IBGE** usou para
janeiro. Ela segue o código e as escolhas do IBGE, não a série longa do projeto:

| Situação da categoria na tabela nova | Âncora da 356 no ano da troca | Casos |
|---|---|---|
| Código que já existia na tabela anterior (mesmo com id SIDRA novo) | encadeia desde janeiro pelo código | quase todos |
| Código novo | começa no primeiro mês da tabela nova (não é acumulado no ano) | 1705 e 7062: todos; 1387: a maioria |
| Código novo na 1387 (2006) com antecessor escolhido pelo IBGE | encadeia desde janeiro pelo antecessor, de outro código | 12: o item 8104 Cursos diversos e os seus 9 subitens ← 8101014 Cursos diversos; 1110010 Frango em pedaços ← 1110011 Peito de frango; 1111011 Queijo ← 1111024 Queijo prato |

Isso aparece de três formas quando se compara com a série longa:

- **Série que continua no mesmo código:** o índice encadeado reproduz a 356, salvo os 34 subitens
  in natura que vêm da cesta variável da 1646 (2006, na 1387; ver abaixo).
- **Série emendada pela revisão em que o código muda** (8 séries, por exemplo Cinema → Cinema,
  teatro e concertos em 2020): a 356 começa na troca. Em 7 delas isso diverge do acumulado da série;
  na oitava (8104002, 2020) o código antigo ficou parado de janeiro à troca e os dois coincidem.
- **Série quebrada pelo projeto no meio do ano da troca com código que já existia** (12 séries,
  por proposta não aceita ou não revisada, por exemplo 1111004 Leite pasteurizado em 2012): a 356
  encadeia pelo código através da quebra. Ela emenda exatamente o que o projeto decidiu não emendar.

**Regra que decorre:** a 356 só vale como acumulado no ano da série longa quando a série tem
janeiro naquele ano e o código de janeiro é o mesmo do mês. Fora disso (série que começa no meio do
ano, ou código que mudou no ano), a 356 não é usada como acumulado da série: usá-la importaria uma
emenda silenciosa (decisão 0005). O índice encadeado já respeita isso, porque só dá o acumulado no
ano quando a série tem janeiro (#42 aplica a regra ao "oficial primeiro").

**Âncoras do IBGE como evidência de harmonização.** As 12 âncoras de outro código mostram ligações
que o próprio IBGE fez: 8101014 → 8104 (subitem que vira item, hoje `descontinuado` + `novo` no
mapa) e Peito de frango → Frango em pedaços (o mapa tem a divisão Frango → Frango inteiro + Frango
em pedaços, aceita na revisão). São evidência para revisão humana, nunca emenda automática (#48).

### 8.3 Marca de cesta variável nas janelas

`cesta_variavel` marca os meses da 1646 cobertos pela exceção A-013. Um acumulado cuja janela
contém mês marcado também não reproduz o IBGE: é o caso da 356 de 2006 dos 34 subitens in natura,
já na 1387, e dos acumulados de 12 meses até jun/2007 (a janela de jul/2007 começa em ago/2006). Na #42, a janela que contém mês marcado
herda a marca.

## 9. Acumulados por janela (#42)

`acumulados_ipca15` (`macroaf.indicators.acumulados`) tem uma linha por série longa, mês e janela
(3, 6, 12, 24 e 36 meses e no ano), com `acumulado`, `origem` (`oficial` ou `calculado`) e
`cesta_variavel`.

- **Calculado:** pelo índice encadeado (seção 8), `(I_t / I_(t-k) − 1) × 100`. A janela que sai do
  início da série fica vazia: o acumulado nunca atravessa uma quebra.
- **Oficial primeiro, onde mede o mesmo:** 1120 (12 meses) e 356 (no ano) da própria categoria; para
  o geral, 1118, 1119, 1120 e 356 da 3065. O oficial vale quando:
  - a janela cabe na série, ou começa antes do início dos dados (mai/2000), o que é falta de dado e
    não quebra;
  - no acumulado no ano, o código de janeiro é o mesmo do mês (A-023, seção 8.2). Série que nasce
    no meio do ano da troca ou que mudou de código no ano fica sem a 356, porque ela atravessaria a
    quebra pelo código;
  - não é valor publicado errado (A-015) que diverge do calculado. Erro publicado é só o mês
    listado em `meses_com_erro_publicado` (6.5): 356 trocada de 2003-02 e de 2004-07 na 1646 e
    1118/1119 da 3065 em 4 meses. Nesses meses vale o calculado, salvo onde o publicado concorda
    com ele (7 linhas em 2003-02, 29 em 2004-07). Os meses seguintes, que a exceção cobre só pela
    âncora (2003-03 e 2004-08), ficam com o oficial em todas as 593 linhas.
  - no acumulado em 12 meses, a 1120 cobre sempre 12 meses da mesma tabela (ela só é publicada
    depois do primeiro ano da 1705 e da 7062, A-009), então não há troca de código dentro da janela.
- **24 e 36 meses** não são publicados: só calculados.
- **Cesta variável:** a janela que contém mês marcado (seção 8.3) herda a marca, por exemplo a 356
  de 2006 dos subitens in natura na 1387 e os acumulados de 12 meses até jun/2007.

Teste: onde o oficial é usado e o calculado existe, os dois concordam dentro do limite de
arredondamento (A-014), fora da cesta variável e da 356 da 1646 e da 1387.

**Ruído da 356 composta desde janeiro (A-024).** Na 1646 e na 1387, a 356 publicada diverge do
acumulado desde janeiro pelo índice acima do arredondamento em 638 linhas fora da cesta variável
(329 na 1646, 309 na 1387; até cerca de 0,25 p.p., só subgrupos, itens e subitens). É mais que os
58 casos da validação (A-016), porque ela compara um passo e esta comparação compõe o ano inteiro.
Fica o oficial: é o número do IBGE e não há erro identificado; a contagem é sentinela em teste.

## 10. Contribuições (#43)

`contribuicoes_ipca15` (`macroaf.indicators.contribuicoes`) tem uma linha por série longa, mês e
janela (`mes` e as janelas da seção 9), com `contribuicao` em pontos percentuais e, no mês,
`participacao_no_grupo` em %.

- **No mês:** `c = peso × v / Σ pesos dos grupos`, peso e variação do mesmo mês e tabela (como na
  reconciliação). Dividir pela soma dos pesos dos grupos, que é 100 salvo o erro de 2010-07/08 na
  1387 (100,1, A-015), faz a soma dos grupos reproduzir a média ponderada.
- **Participação no grupo:** a contribuição dividida pela soma das contribuições do mesmo nível no
  mesmo grupo. Soma 100% por construção; com variação do grupo perto de zero, as participações
  ficam grandes e de sinais opostos, e devem ser lidas com cuidado.
- **Para o acumulado:** `Σ_m c_m × I_geral(m−1) / I_geral(início − 1)` sobre os meses da janela. A
  contribuição acumulada do geral é exatamente o seu acumulado calculado (seção 9), e a soma dos
  grupos difere dele no máximo pela soma, reescalada, dos limites mensais da reconciliação. A janela
  não sai da série longa da categoria (decisão 0005).
- **Cesta variável:** subitens in natura da 1646 ficam sem contribuição; o produto entra pelo item
  (A-013).

Conferência: no mês, a soma dos grupos difere do geral em no máximo 0,007 p.p., dentro do limite da
reconciliação em todos os 317 meses.

## 11. Registro de descobertas

Toda descoberta sobre os dados ou o método segue o ciclo de [`aprendizados.md`](aprendizados.md):
entra como A-NNN, é promovida para teste ou validação quando possível e, se muda o método, é
registrada neste documento com a regra que dela decorre.
