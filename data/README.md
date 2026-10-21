# Dados

As camadas separam proveniência, processamento e consumo. Dentro delas, a organização considera
fonte ou índice conforme a finalidade. A proposta de evolução está em
[`docs/ESTRUTURA.md`](../docs/ESTRUTURA.md); os caminhos abaixo são os **atuais**.

| Camada | Caminho | Conteúdo | Versionado? |
|---|---|---|---|
| Original | `raw/ibge_sidra/<tabela>/` | Respostas oficiais por mês, metadados e revisões gzip | Sim |
| Preparação | `staging/<indice>/` | Dimensão, fato, referência, série longa, indicadores e validações | Não; recriado do raw |
| Consumo | `marts/<indice>_*.csv` | Cinco tabelas por índice, com nomes públicos estáveis | Sim |
| Catálogo da publicação | `metadata.json` | Cobertura, coleta, validações, contagens e hashes por índice | Sim |

O raw usa `manifesto.csv` por fonte, com URL, coleta e SHA-256 do corpo original. Cada revisão
fica ao lado da anterior; não editar nem apagar respostas para corrigir resultados. O staging
é descartável, mas não o raw, as decisões em `reference/` ou o histórico de séries.

## Escolher um índice

| Índice | Detalhe publicado na carga de 20/10/2026 | Dicionário | Referência do geral |
|---|---|---|---|
| IPCA-15 | mai/2000–set/2026 | [README dos marts](marts/README.md) | SIDRA 3065 |
| IPCA | jul/2006–set/2026 | [ipca_README.md](marts/ipca_README.md) | SIDRA 1737 |

As datas são um retrato desta revisão. Use [`metadata.json`](metadata.json) para a publicação
corrente. A referência do IPCA começa em 1979 no raw, mas não fornece detalhe por categoria
antes de julho/2006 nesta entrega. IPCA e IPCA-15 têm calendários e classificações próprios.

## Escolher uma tabela de consumo

Substitua `<indice>` por `ipca` ou `ipca15`:

| CSV | Uso | Chave |
|---|---|---|
| `<indice>_categorias.csv` | Classificação, série longa e seus limites | `chave_categoria` |
| `<indice>_mensal.csv` | Oficiais mensais, índice, contribuição mensal e sazonalidade | `mes`, `chave_categoria` |
| `<indice>_acumulados.csv` | Acumulados e origem de cada janela | `mes`, `chave_categoria` |
| `<indice>_contribuicoes.csv` | Contribuições acumuladas em pontos percentuais | `mes`, `chave_categoria` |
| `<indice>_difusao.csv` | Difusão no geral e por grupo | `mes`, `codigo_ibge` |

Leia códigos como texto, preservando sua identidade. `serie_id` é atributo da categoria e pode
mudar após revisão; não substitui a chave publicada. Para alimentos, use os descendentes de
`codigo_ibge` 1, 11 e 12 (grupo e subgrupos) no índice escolhido, respeitando o nível de agregação.
Não some simultaneamente pais e filhos, pois isso conta a mesma informação mais de uma vez.

## Consumo e reprodução

Os CSVs são UTF-8, separados por vírgula, com ponto decimal. Consulte o dicionário de cada índice
para unidades, ausentes, origem dos acumulados e marcas de qualidade. Os cinco arquivos e os
metadados devem ser lidos da mesma publicação; para reproduzir uma análise, registre o commit.
No GitHub, use URLs `raw.githubusercontent.com` para CSVs; a página `blob` serve à navegação.

As URLs de `marts/` são contratos existentes do Power BI. Esta revisão não move os arquivos nem
cria cópias. Para atualizar ou reconstruir, consulte [Operação](../docs/OPERACAO.md).
Os [termos dos dados](../LICENSE-DADOS.md) distinguem derivados e originais.
