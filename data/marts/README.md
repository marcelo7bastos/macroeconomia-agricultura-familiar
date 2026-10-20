# Marts do IPCA-15

Gerado por `uv run python -m macroaf.marts.publicar --indice ipca15`. Não edite à mão.

Dados até **2026-09**. CSV em UTF-8, separador vírgula, ponto decimal; no Power Query,
leia com `Csv.Document(..., [Delimiter=",", Encoding=65001])` e tipe as colunas numéricas
com a cultura `"en-US"`. Os nomes dos arquivos e das colunas são estáveis: colunas só são
acrescentadas (decisões 0006 e 0007). Os relacionamentos usam `chave_categoria`, nunca
`serie_id`, que muda quando a revisão da harmonização junta ou separa séries.

Os valores oficiais passam como publicados. Os calculados são arredondados: 6 casas no
índice e nas contribuições; 4 nos acumulados, na participação no grupo e na sazonalidade; 2 na
difusão.

Atualização: automática, quando o IBGE divulga um mês novo ou revisa um dos últimos meses
(workflow `.github/workflows/atualizacao.yml`); `data/metadata.json` diz o último mês e a
data da coleta.

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
| `nivel_hierarquico` | Pelo número de dígitos do código. Valores: `geral`, `grupo`, `subgrupo`, `item`, `subitem`. |
| `codigo_pai` | Código IBGE do nível de cima. |
| `grupo` | Código do grupo (1 dígito). |
| `subgrupo` | Código do subgrupo (2 dígitos). |
| `item` | Código do item (4 dígitos). |
| `serie_id` | Série longa a que a categoria pertence. Atributo de agrupamento: muda quando a revisão da harmonização junta ou separa séries (histórico em reference/historico_series_<indice>.csv). |
| `serie_nome` | Nome da categoria mais recente da série. |
| `serie_inicio` | Primeiro mês da série longa. |
| `serie_fim` | Último mês da série longa. |
| `serie_entrada` | Como a série começa (o tipo da ligação; "(proposta rejeitada)" quando a revisão não aceitou a emenda). Valores: `inicio dos dados`, `novo`, `fundido`, `dividido`, `renomeado (proposta rejeitada)`, `fundido (proposta rejeitada)`, `dividido (proposta rejeitada)`. |
| `serie_saida` | Como a série termina (idem). Valores: `em curso`, `descontinuado`, `fundido`, `dividido`, `renomeado (proposta rejeitada)`, `fundido (proposta rejeitada)`, `dividido (proposta rejeitada)`. |

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
| `variacao_acum_12m_publicada` | Acumulado em 12 meses publicado (1120) na tabela da categoria; vazio onde ela não publica (no geral, a 3065 publica: ver acumulados.acum_12m). |
| `indice_base_100` | Índice encadeado da série longa: 100 no mês anterior ao início da série (#41). |
| `contribuicao_pp` | Contribuição para a variação do geral no mês, em pontos percentuais (#43). Vazia nos subitens in natura da 1646, que entram pelo item (A-013). |
| `participacao_no_grupo` | % da soma das contribuições do mesmo nível no mesmo grupo. Vazia no geral e onde falta alguma contribuição no nível e grupo (A-025); nos grupos, sempre 100. |
| `sazonalidade_media` | Média da variação deste mês do ano nos 5 anos da série que terminam neste mês, inclusive (#44). Vazia sem 5 anos seguidos na série. |
| `sazonalidade_mediana` | Mediana da variação deste mês do ano nos mesmos 5 anos. |
| `cesta_variavel` | 1 se este mês tem cesta variável (in natura da POF 1995-96, A-013). |
| `sazonalidade_cesta_variavel` | 1 se a janela de 5 anos da sazonalidade contém mês com cesta variável. |

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
| `origem_3m` | oficial ou calculado, para acum_3m. Valores: `oficial`, `calculado`. |
| `origem_6m` | oficial ou calculado, para acum_6m. Valores: `oficial`, `calculado`. |
| `origem_12m` | oficial ou calculado, para acum_12m. Valores: `oficial`, `calculado`. |
| `origem_24m` | oficial ou calculado, para acum_24m. Valores: `oficial`, `calculado`. |
| `origem_36m` | oficial ou calculado, para acum_36m. Valores: `oficial`, `calculado`. |
| `origem_ano` | oficial ou calculado, para acum_ano. Valores: `oficial`, `calculado`. |
| `cesta_variavel_janelas` | Janelas que contêm mês com cesta variável, separadas por ponto e vírgula (A-013). |

## `ipca15_contribuicoes.csv`

Uma linha por mês e categoria: contribuição para o acumulado do geral em cada janela, em pontos percentuais (#43). Os subitens in natura da 1646 não têm contribuição (entram pelo item, A-013), então nenhuma janela aqui depende de cesta variável.

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
