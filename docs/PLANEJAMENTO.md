# Planejamento

Documento vivo. Decisões tomadas ficam na seção 9 (contexto completo em [`decisoes/`](decisoes/));
lições aprendidas ficam em [`aprendizados.md`](aprendizados.md); ideias e frentes futuras ficam como
[issues com o rótulo `backlog`](https://github.com/marcelo7bastos/macroeconomia-agricultura-familiar/issues?q=label%3Abacklog).

## 1. Objetivo

Pipeline aberto e reprodutível que coleta indicadores macroeconômicos ligados à agricultura e à
agricultura familiar, transforma os dados em tabelas padronizadas e calcula indicadores validados.
O resultado alimenta um site estático e pode ser lido diretamente pelo Power BI.

Princípios:

1. **Dado oficial primeiro.** Só calculamos o que o IBGE/BCB não publica.
2. **Todo indicador calculado tem teste** contra uma referência oficial ou uma identidade contábil.
3. **Reprodutível a partir do código.** Nenhuma planilha manual fora do repositório; nenhum link
   de planilha como fonte.
4. **Nenhuma série é emendada em silêncio.** Quebras de série são marcadas, não escondidas.

## 2. Escopo

| Fase | Tema | Situação |
|---|---|---|
| **Piloto** | **IPCA-15** completo (mai/2000 → atual), até o nível de subitem | em andamento |
| Backlog | IPCA cheio | issue |
| Backlog | PIB total e agropecuária, Selic, câmbio, IGPs | issues |
| Backlog | Agricultura familiar: participação na produção (Censo Agro 2017), crédito Pronaf | issues |
| Backlog | Indicador de inflação dos alimentos da agricultura familiar | issue |
| Backlog | Produção e preços agrícolas (LSPA, PAM, Conab) | issue |
| Backlog | Site (Quarto + GitHub Pages) e consumo pelo Power BI | issues |

O IPCA-15 foi escolhido como piloto por ter a mesma estrutura do IPCA cheio (mesma classificação
c315, mesmas trocas de POF), em volume um pouco menor. Tudo o que for construído para ele deve ser
reaproveitável para o IPCA cheio trocando apenas a configuração.

## 3. Extração (piloto IPCA-15)

### 3.1 Tabelas SIDRA (conferidas na API do IBGE em 19/10/2026)

Detalhes e peculiaridades na ficha [`indices/ipca15.md`](indices/ipca15.md).

| Tabela | Período | Estrutura de pesos | Variáveis |
|---|---|---|---|
| 1646 | mai/2000 → jul/2006 | POF 1995-96 | 355 var. mensal, 356 acum. ano, 357 peso |
| 1387 | ago/2006 → jan/2012 | POF 2002-03 | 355, 356, 357 |
| 1705 | fev/2012 → jan/2020 | POF 2008-09 | 355, 356, 1120 acum. 12 meses, 357 |
| 7062 | fev/2020 → atual | POF 2017-18 | 355, 356, 1120, 357 |
| 3065 | mai/2000 → atual | — (só índice geral) | 1117 número-índice, 355, 1118 acum. 3m, 1119 acum. 6m, 356, 1120 |

A tabela 3065 é a **referência oficial** para validar o índice geral e os acumulados calculados.

Quantidade de categorias da classificação 315 por tabela (pela API de metadados):

Contagem pelo código IBGE no nome da categoria (conferida em 19/10/2026; todas têm 1 geral, sem
código):

| Tabela | Grupos | Subgrupos | Itens | Subitens | Total |
|---|---|---|---|---|---|
| 7062 | 9 | 19 | 51 | 367 | 447 |
| 1705 | 9 | 19 | 52 | 365 | 446 |
| 1387 | 9 | 19 | 52 | 384 | 465 |
| 1646 | 9 | 19 | 52 | 512 | 593 |

A contagem antiga de 383 subitens na 1387 vinha do campo `nivel`: o subitem `4103031.Conjunto
infantil` aparece com `nivel = 0` (ver A-001 e 3.3).

A variável 1120 (acumulado em 12 meses) existe nos metadados da 1705 e da 7062, mas vem `...` em
parte do período (1705 até fev/2017; 7062 até dez/2020). O acumulado por categoria nesses meses é
calculado e conferido com a 3065 no índice geral (A-009).

Metadados: `https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados`
(árvore de classificação e último período disponível).

### 3.2 Como extrair

Detalhes e alternativas na [decisão 0003](decisoes/0003-extracao-incremental.md).

- **Comando:** `uv run python -m macroaf.extract.atualizar` (`--verificar` só confere).
- **Conferência do catálogo:** `periodicidade` dos metadados de cada tabela é comparada com o
  catálogo (início sempre; fim das tabelas fechadas). Divergência interrompe antes de baixar.
- **Extração incremental:** baixa só os meses ausentes no raw, uma requisição por tabela × mês
  (cerca de 1.800 valores, bem abaixo do limite da API). Sem mês novo → não baixa valores.
- **Revisões:** nas tabelas abertas, os 3 últimos meses são baixados de novo; conteúdo diferente
  vira `<AAAAMM>.r2.json.gz`, sem apagar o anterior.
- **Resiliência:** retentativas com espera exponencial em erro de rede, 429 e 5xx; timeout
  explícito; erro 400 do SIDRA é definitivo.
- **Camada `raw`:** `data/raw/<fonte>/<tabela>/<AAAAMM>.json.gz`, corpo exato da resposta
  compactado, com `manifesto.csv` (URL, data da coleta, SHA-256 do original, registros). **É
  versionada no repositório** (decisão 9.1).
- **Catálogo `config/series.yaml`:** cada série descrita por fonte, tabela, variáveis, período,
  unidade e versão da POF. Incluir série nova = editar o YAML. O esquema é validado por
  `macroaf.catalogo.carregar_catalogo` (tabelas de dados em sucessão mês a mês, sem lacuna nem
  sobreposição; variáveis descritas; POF sem repetição) e testado em `tests/test_catalogo.py`.

### 3.3 Lições do modelo Power BI anterior

O projeto anterior (fora deste repositório) foi auditado; o que muda aqui:

- **Hierarquia pelo código, não pelo campo `nivel`.** O campo `nivel` dos metadados muda de
  numeração entre tabelas (7062/1705 começam em 0 = geral; 1646/1387 usam outra escala). O código
  IBGE no nome da categoria (ex.: `1101002.Arroz`) é estável: 1 dígito = grupo, 2 = subgrupo,
  4 = item, 7 = subitem.
- **IPCA-15 tem classificação própria.** Em 7062 são 367 subitens; no IPCA cheio (7060), 377. O
  modelo anterior reaproveitava a classificação do IPCA cheio e perdia categorias do IPCA-15.
- **Nada de calendário com data final fixa** e nada de agregações que contam a mesma linha mais de
  uma vez: cada indicador calculado tem teste de identidade (seção 4.4).
- **Fontes só por API oficial ou CSV versionado.** Links de planilha do Google Drive foram a
  principal fonte de fragilidade.

## 4. Transformação

### 4.1 Camadas

```
data/raw/       JSON original da API, compactado e imutável (auditoria, versionado)
data/staging/   tabelas tidy, tipadas, uma linha por observação (recriado do raw, não versionado)
data/marts/     indicadores prontos para consumo (site e Power BI, versionado)
```

### 4.2 Tabelas de staging

**`dim_classificacao`**: uma linha por categoria em cada versão de POF.
`versao_pof | tabela_sidra | codigo_sidra | codigo_ibge | nome | nivel_hierarquico | codigo_pai | grupo | subgrupo | item`

- `codigo_sidra` é o id da categoria na API (ex.: 7169); `codigo_ibge` é o código no nome
  (`1101002`), com `0` para o índice geral por convenção do projeto.
- `nivel_hierarquico ∈ {geral, grupo, subgrupo, item, subitem}`, derivado do número de dígitos.
- `grupo`, `subgrupo`, `item`: código do nível a que a categoria pertence (ela mesma, se for
  daquele nível); vazio acima dele.
- Gerada por `uv run python -m macroaf.transform.classificacao` a partir dos metadados no raw;
  contrato `pandera` em `macroaf.transform.classificacao.ESQUEMA`.

**`fato_ipca15`**: uma linha por mês e categoria, variáveis em colunas.
`mes | versao_pof | tabela_sidra | codigo_sidra | codigo_ibge | nivel_hierarquico | variacao_mensal | variacao_acum_ano | variacao_acum_12m | peso`

Ligado à `dim_classificacao` por `(tabela_sidra, codigo_sidra)` (METODOLOGIA.md, 2.2).
`ref_ipca15_geral` guarda a tabela 3065 (número-índice e acumulados do geral) para as validações.

**`map_harmonizacao`** (`reference/map_harmonizacao_ipca15.csv`, versionado): correspondência
entre categorias de POFs consecutivas, por código IBGE **e** id SIDRA, com
`tipo_correspondencia ∈ {identico, renomeado, dividido, fundido, descontinuado, novo}`,
`situacao ∈ {automatico, proposto, revisado}`, critério, pesos nas pontas e revisor.

**`serie_longa_ipca15`**: as linhas do fato com `serie_id`, início, fim, entrada e saída de cada
série longa (METODOLOGIA.md, seção 7).

### 4.3 Granularidade e séries longas (decisão 9.2)

A maior granularidade publicada pelo IBGE é o **subitem** (5 níveis: geral, grupo, subgrupo,
item, subitem). O modelo Power BI anterior já usava o subitem como folha da hierarquia.

- Até **subgrupo**, a estrutura é quase estável entre POFs; os poucos casos que mudam (subgrupo
  `72`, itens `1117` e `7203`) passam pela harmonização como os demais (A-020).
- **Item e subitem** mudam a cada POF. A série longa é montada a partir do `map_harmonizacao`:
  - `identico`/`renomeado` → série contínua;
  - `dividido`/`fundido` → série contínua no nível agregado, com marcação de quebra no detalhe;
  - `descontinuado`/`novo` → série termina/começa, sem emenda.
- O mapeamento é gerado de forma semiautomática (código + id + nome) e **revisado manualmente**;
  o resultado revisado fica em `reference/` e é versionado. **Na dúvida, quebra**: proposta não
  revisada não emenda (decisão 0005).

### 4.4 Validações (bloqueiam a publicação se falharem)

Limites, exceções e as descobertas que os justificam: [METODOLOGIA.md, seção 6](METODOLOGIA.md#6-validações).

1. **Esquema:** colunas, tipos, nulos e faixas plausíveis.
2. **Pesos:** em cada mês, grupos somam 100 e filhos somam o peso do pai.
3. **Reconciliação:** média ponderada dos filhos (peso × variação) reproduz a variação oficial do
   pai e do índice geral.
4. **Continuidade:** nenhum mês faltando por série ativa.

Na #5, a tolerância fixa prevista (0,01 p.p.) foi substituída pelo **limite analítico de
arredondamento** de cada conta (A-014), com exceções documentadas e contadas.
5. **Acumulados:** acumulados calculados a partir das variações mensais batem com as variáveis
   oficiais (356, 1120 e, para o geral, 1118/1119 da tabela 3065).
6. **Costura entre tabelas:** o índice geral encadeado pelas quatro tabelas reproduz o
   número-índice da tabela 3065.

## 5. Indicadores do piloto

### 5.1 Oficiais (organizados, não recalculados)

Variação mensal, acumulada no ano, acumulada em 12 meses e peso, para todos os níveis.

### 5.2 Calculados

| Indicador | Definição | Teste |
|---|---|---|
| Contribuição (p.p.) | `peso × variação / 100` | soma dos grupos = índice geral |
| Contribuição dentro do grupo | participação do subitem na variação do grupo (ex.: Alimentação e bebidas) | soma = 100% |
| Acumulados em janelas | 3, 6, 24, 36 meses, compondo as variações mensais | 3/6/12 batem com a tabela 3065 |
| Difusão | % de subitens com variação positiva (simples e ponderada) | 0 ≤ x ≤ 100 |
| Sazonalidade | média e mediana da variação por mês do ano, em janela móvel | — |
| Índice base 100 | número-índice por categoria a partir de data escolhida | geral bate com 3065 |

## 6. Saídas

- `data/marts/*.parquet` e `*.csv`, com **nomes de arquivo estáveis** (URLs do raw do GitHub não
  mudam; o Power BI lê direto delas).
- `data/marts/README.md` gerado automaticamente: dicionário de dados.
- `data/metadata.json`: último mês por série, data da coleta, resultado das validações.

## 7. Stack

- Python 3.12, ambiente com `uv`.
- `httpx` + `tenacity` (coleta), `pandas` + `pyarrow` (dados), `pandera` (contratos),
  `pytest`, `ruff`.
- GitHub Actions: agendamento diário na janela de divulgação, `workflow_dispatch`,
  `permissions: contents: write`; só faz commit quando há mês novo e as validações passam.
- Site (backlog): Quarto + GitHub Pages.

Estrutura prevista:

```
config/series.yaml
src/macroaf/
  extract/      atualizar.py (comando), sidra.py, ibge_metadados.py, raw.py, cliente.py
  transform/    classificacao.py, ipca15.py, harmonizacao.py
  indicators/   contribuicao.py, acumulados.py, difusao.py, sazonalidade.py
  validate/
data/{raw,staging,marts}/
reference/      mapeamentos revisados manualmente
tests/
docs/           PLANEJAMENTO.md, METODOLOGIA.md, AGENTES.md, aprendizados.md,
                decisoes/, indices/, fontes/
.claude/        agents/, skills/, hooks/ (ver docs/AGENTES.md)
.github/workflows/atualizacao.yml
```

## 8. Roteiro do piloto

Cada etapa é uma issue do marco **Piloto IPCA-15**.

0. Agentes, skills e registro de aprendizado ([`AGENTES.md`](AGENTES.md)).
1. Base do repositório: estrutura, `uv`, `pytest`, `ruff`, CI.
2. Catálogo de séries (`config/series.yaml`).
3. Extração SIDRA + metadados, com camada `raw` (inclui testar a API a partir do runner do GitHub).
4. `dim_classificacao` pelas quatro tabelas.
5. `fato_ipca15` e validações.
6. Harmonização entre POFs até subitem.
7. Indicadores calculados.
8. Saídas (`marts`, dicionário, `metadata.json`).
9. Workflow de atualização automática.

## 9. Decisões

| # | Decisão | Situação |
|---|---|---|
| 9.1 | Guardar o `raw` no repositório | **Sim** |
| 9.2 | Granularidade da série longa | **Até subitem** (maior publicada), via harmonização revisada |
| 9.3 | Método do indicador de agricultura familiar (ponderação contínua × corte) | **Em aberto**: issue de backlog |
| 9.4 | Idioma de código e dados | **Português** |
| 9.5 | Licenças | **MIT** (código) e **CC BY 4.0** (dados derivados) |
| 9.6 | Memória dos agentes | **No próprio repositório** ([0001](decisoes/0001-memoria-dos-agentes-no-repositorio.md)) |
| 9.7 | Organização dos agentes | **Por função, não por índice** ([0002](decisoes/0002-agentes-por-funcao.md)) |
| 9.8 | Atualização dos dados | **Extração incremental, raw compactado e imutável, compilação completa** ([0003](decisoes/0003-extracao-incremental.md)) |
| 9.9 | Documentação das transformações | **Página HTML por índice, em degraus, gerada dos dados** ([0004](decisoes/0004-explicacao-em-degraus.md)) |
| 9.10 | Emenda de séries entre POFs | **Na dúvida, quebra**: só emenda com prova ou revisão humana ([0005](decisoes/0005-na-duvida-quebra.md)) |
| 9.11 | Chave dos marts | **Categoria publicada (tabela e id SIDRA) e mês**; a série longa é atributo ([0006](decisoes/0006-chave-estavel-dos-marts.md)) |
