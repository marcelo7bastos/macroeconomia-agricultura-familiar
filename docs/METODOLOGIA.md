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
- A variável 1120 (acumulado em 12 meses) consta nos metadados, mas vem `...` em 2012-02 a
  2017-02 (1705) e 2020-02 a 2020-12 (7062), e não existe na 1646 nem na 1387 (A-009). Nesses
  meses o acumulado em 12 meses é calculado (seção 6) e conferido com a 3065 no índice geral.

## 5. Tabelas de staging

Geradas por `uv run python -m macroaf.transform.ipca15` a partir do raw, sem rede. Colunas e
semântica na seção 4.2 do [planejamento](PLANEJAMENTO.md).

- `dim_classificacao`: uma linha por categoria e tabela.
- `fato_ipca15`: uma linha por mês e categoria; variáveis em colunas.
- `ref_ipca15_geral`: tabela 3065 (número-índice e acumulados do índice geral).

## 6. Validações

Ver seção 4.4 do planejamento. Tolerâncias e exceções calibradas com os dados reais na #5
(seção a completar neste PR).

## 7. Registro de descobertas

Toda descoberta sobre os dados ou o método segue o ciclo de [`aprendizados.md`](aprendizados.md):
entra como A-NNN, é promovida para teste ou validação quando possível e, se muda o método, é
registrada neste documento com a regra que dela decorre.
