# Marts do IPCA-15

Gerado por `uv run python -m macroaf.marts.publicar --indice ipca15`. Não edite à mão.

Dados até **2026-09**. CSV em UTF-8, separador vírgula, ponto decimal; no Power Query,
leia com `Csv.Document(..., [Delimiter=",", Encoding=65001])` e tipe as colunas numéricas
com a cultura `"en-US"`. Os nomes dos arquivos e das colunas são estáveis: colunas só são
acrescentadas (decisões 0006 e 0007). Os relacionamentos usam `chave_categoria`, nunca
`serie_id`, que muda quando a revisão da harmonização junta ou separa séries.

Metodologia: [`docs/METODOLOGIA.md`](../../docs/METODOLOGIA.md). Explicação passo a passo:
[`docs/transformacoes/ipca15.html`](../../docs/transformacoes/ipca15.html).

## `ipca15_categorias.csv`

Uma linha por categoria publicada (tabela SIDRA e id). Dimensão dos outros arquivos.

Chave: `chave_categoria`. Linhas: 1.951.

| Coluna | Descrição |
|---|---|
| `chave_categoria` | Identidade publicada pelo IBGE: `<tabela>.<id SIDRA>` (decisão 0006). Chave estável. |
| `tabela_sidra` | Tabela do SIDRA (uma por POF). |
| `codigo_sidra` | Id SIDRA da categoria nessa tabela. |
| `versao_pof` | POF que define a cesta e os pesos da tabela. |
| `codigo_ibge` | Código da categoria na classificação 315 (0 = índice geral). |
| `nome` | Nome da categoria como o IBGE publica. |
| `nivel_hierarquico` | geral, grupo, subgrupo, item ou subitem (pelo número de dígitos do código). |
| `codigo_pai` | Código IBGE do nível de cima. |
| `grupo` | Código do grupo (1 dígito). |
| `subgrupo` | Código do subgrupo (2 dígitos). |
| `item` | Código do item (4 dígitos). |
| `serie_id` | Série longa a que a categoria pertence. Atributo de agrupamento: muda quando a revisão da harmonização junta ou separa séries (histórico em reference/historico_series_<indice>.csv). |
| `serie_nome` | Nome da categoria mais recente da série. |
| `serie_inicio` | Primeiro mês da série longa. |
| `serie_fim` | Último mês da série longa. |
| `serie_entrada` | Como a série começa: início dos dados, novo, fundido, dividido ou proposta rejeitada. |
| `serie_saida` | Como a série termina: em curso, descontinuado, fundido, dividido ou proposta rejeitada. |

## `ipca15_mensal.csv`

Uma linha por mês e categoria: valores oficiais do mês e indicadores da série longa.

Chave: `mes. chave_categoria`. Linhas: 153.741.

| Coluna | Descrição |
|---|---|
| `mes` | Mês de referência (AAAA-MM). |
| `chave_categoria` | Categoria (ver categorias). |
| `variacao_mensal` | Variação no mês, em %, como publicada (variável 355). |
| `peso` | Peso no mês, em % do índice geral, como publicado (357). |
| `variacao_acum_ano_publicada` | Acumulado no ano publicado (356), sem tratamento. Para o acumulado da série, use acumulados.acum_ano (A-023). |
| `variacao_acum_12m_publicada` | Acumulado em 12 meses publicado (1120), vazio onde o IBGE não publica. |
| `indice_base_100` | Índice encadeado da série longa: 100 no mês anterior ao início da série (#41). |
| `contribuicao_pp` | Contribuição para a variação do geral no mês, em pontos percentuais (#43). |
| `participacao_no_grupo` | % da soma das contribuições do mesmo nível no mesmo grupo; vazia onde falta alguma contribuição (A-025). |
| `sazonalidade_media` | Média da variação deste mês do ano nos últimos 5 anos da série, até este mês (#44). |
| `sazonalidade_mediana` | Mediana da variação deste mês do ano nos últimos 5 anos da série, até este mês. |
| `cesta_variavel` | 1 se o mês tem cesta variável (in natura da POF 1995-96, A-013). |

## `ipca15_acumulados.csv`

Uma linha por mês e categoria: acumulados por janela, oficial onde mede o mesmo que a série longa, calculado pelo índice onde falta ou onde o oficial não serve (#42).

Chave: `mes. chave_categoria`. Linhas: 153.465.

| Coluna | Descrição |
|---|---|
| `mes` | Mês de referência (AAAA-MM). |
| `chave_categoria` | Categoria (ver categorias). |
| `acum_3m` | Acumulado em 3 meses, em %. |
| `acum_6m` | Acumulado em 6 meses, em %. |
| `acum_12m` | Acumulado em 12 meses, em %. |
| `acum_24m` | Acumulado em 24 meses, em %. |
| `acum_36m` | Acumulado em 36 meses, em %. |
| `acum_ano` | Acumulado em no ano, em %. |
| `origem_3m` | oficial ou calculado, para acum_3m. |
| `origem_6m` | oficial ou calculado, para acum_6m. |
| `origem_12m` | oficial ou calculado, para acum_12m. |
| `origem_24m` | oficial ou calculado, para acum_24m. |
| `origem_36m` | oficial ou calculado, para acum_36m. |
| `origem_ano` | oficial ou calculado, para acum_ano. |
| `cesta_variavel_janelas` | Janelas que contêm mês com cesta variável, separadas por ponto e vírgula (A-013). |

## `ipca15_contribuicoes.csv`

Uma linha por mês e categoria: contribuição para o acumulado do geral em cada janela, em pontos percentuais (#43).

Chave: `mes. chave_categoria`. Linhas: 148.337.

| Coluna | Descrição |
|---|---|
| `mes` | Mês de referência (AAAA-MM). |
| `chave_categoria` | Categoria (ver categorias). |
| `contrib_3m` | Contribuição para o acumulado do geral em 3 meses, em p.p. |
| `contrib_6m` | Contribuição para o acumulado do geral em 6 meses, em p.p. |
| `contrib_12m` | Contribuição para o acumulado do geral em 12 meses, em p.p. |
| `contrib_24m` | Contribuição para o acumulado do geral em 24 meses, em p.p. |
| `contrib_36m` | Contribuição para o acumulado do geral em 36 meses, em p.p. |
| `contrib_ano` | Contribuição para o acumulado do geral em no ano, em p.p. |

## `ipca15_difusao.csv`

Uma linha por mês e recorte: porcentagem dos subitens com alta de preço (#44).

Chave: `mes. codigo_ibge`. Linhas: 3.170.

| Coluna | Descrição |
|---|---|
| `mes` | Mês de referência (AAAA-MM). |
| `codigo_ibge` | Recorte: 0 = índice geral; 1 a 9 = grupo. |
| `tabela_sidra` | Tabela do mês (a cesta é a da POF vigente). |
| `versao_pof` | POF da cesta. |
| `cesta_nova` | 1 no primeiro mês de uma POF nova. |
| `subitens` | Subitens coletados (peso maior que zero). |
| `subitens_peso_zero` | Subitens com peso 0, fora da conta (A-026). |
| `positivos` | Subitens coletados com variação maior que zero. |
| `difusao_simples` | positivos / subitens, em %. |
| `difusao_ponderada` | Peso dos positivos / peso dos subitens, em %. |
