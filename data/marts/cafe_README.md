# Dicionário dos marts: café

Gerado por `uv run python -m macroaf.cafe.publicar`; não edite à mão. Projeto: [piloto do café](../../docs/projetos/cafe-piloto.md) (#62).

Preços internacionais (FMI e Banco Mundial) convertidos para R$ por saca de 60 kg pela PTAX média oficial do mês (Banco Central), ao lado dos subitens do IPCA. Os valores do IPCA são os do mart `ipca_mensal.csv`, sem recálculo.

## Séries

| `serie` | Nome | Fonte | Unidade original | Primeiro mês | Último mês |
|---|---|---|---|---|---|
| `cafe_arabica_fmi` | Café arábica (outros suaves), preço internacional | `fmi_pcps` | US¢/lb | 2006-07 | 2026-09 |
| `cafe_robusta_fmi` | Café robusta, preço internacional | `fmi_pcps` | US¢/lb | 2006-07 | 2026-09 |
| `cafe_arabica_bm` | Café arábica (OIC, outros suaves), preço internacional | `banco_mundial_cmo` | US$/kg | 2006-07 | 2026-10 |
| `cafe_robusta_bm` | Café robusta (OIC), preço internacional | `banco_mundial_cmo` | US$/kg | 2006-07 | 2026-10 |
| `ipca_cafe_da_manha` | Café da manhã | `ipca` | — | 2006-07 | 2019-12 |
| `ipca_cafe_moido` | Café moído | `ipca` | — | 2006-07 | 2026-09 |
| `ipca_cafe_soluvel` | Café solúvel | `ipca` | — | 2006-07 | 2026-09 |
| `ipca_cafezinho` | Cafezinho | `ipca` | — | 2006-07 | 2026-09 |
| `ipca_geral` | Índice geral | `ipca` | — | 2006-07 | 2026-09 |

## `cafe_mensal.csv`

Chave: `mes`, `serie`.

| Coluna | Descrição |
|---|---|
| `mes` | Mês de referência, AAAA-MM. |
| `serie` | Identificador estável da série (ver tabela de séries). |
| `nome` | Nome da série. |
| `lado` | `internacional` (preço de mercado) ou `consumidor` (IPCA). |
| `fonte` | `fmi_pcps`, `banco_mundial_cmo` ou `ipca`. |
| `chave_categoria` | Só no IPCA: chave da categoria em `ipca_categorias.csv` (tabela.codigo SIDRA). |
| `unidade_original` | Unidade publicada pela fonte (`US¢/lb` no FMI, `US$/kg` no Banco Mundial). |
| `valor_original` | Preço como publicado pela fonte, na unidade original. Oficial. |
| `ptax_media` | Média mensal oficial da PTAX venda (R$/US$), série SGS 3698, usada na conversão. Oficial; a média calculada dos dias úteis da série SGS 1 a valida. |
| `preco_usd_kg` | Preço em US$/kg (FMI: US¢/lb ÷ 100 ÷ 0,45359237). Calculado. |
| `preco_brl_saca` | Preço em R$ por saca de 60 kg: `preco_usd_kg × ptax_media × 60`. Calculado. |
| `variacao_mensal` | Variação mensal, %. No IPCA, a oficial; nos preços, a do `preco_brl_saca` (calculada). |
| `variacao_acum_12m` | Variação acumulada em 12 meses, %. No IPCA, a oficial onde o IBGE publica; nos demais meses e nos preços, calculada pelo número-índice. A origem está em `origem_acum_12m`. |
| `origem_acum_12m` | `oficial` (variável do IBGE, repetida de `ipca_mensal.csv`) ou `calculado`; vazio sem acumulado. |
| `indice_base_100` | Número-índice com base no mês anterior ao início (2006-06 = 100). No IPCA, o do mart `ipca_mensal.csv`; nos preços, `preco_brl_saca` ÷ preço do mês-base × 100 (calculado). |
| `preco_real_brl_saca` | `preco_brl_saca` a preços do último mês do IPCA, deflacionado pelo índice geral. Vazio depois do último mês do IPCA. Calculado. |
| `razao_consumidor_preco` | Índice do subitem Café moído (IPCA) ÷ índice do preço internacional × 100. Acima de 100: o consumidor acumulou mais alta que o preço internacional em reais desde 2006-06. Leitura de direção, não de margem. Calculado. |

## `cafe_defasagens.csv`

Chave: `serie`, `medida`, `defasagem_meses`.

| Coluna | Descrição |
|---|---|
| `serie` | Série de preço internacional. |
| `medida` | `variacao_mensal` ou `variacao_acum_12m` (as duas em R$). |
| `defasagem_meses` | k: o preço no mês t-k comparado com o subitem Café moído no mês t. |
| `correlacao` | Correlação de Pearson entre as duas medidas. Descritiva, sem leitura causal; no acumulado em 12 meses as janelas se sobrepõem e a correlação fica inflada. Calculado. |
| `observacoes` | Número de pares de meses usados. |
| `inicio` | Primeiro mês t do intervalo comum. |
| `fim` | Último mês t do intervalo comum. |

## Fontes e licenças

- **Banco Central do Brasil - Sistema Gerenciador de Séries Temporais (SGS)** — dado público do Banco Central do Brasil, citar a fonte. Ficha: `docs/fontes/bcb-sgs.md`.
- **Fundo Monetário Internacional - Primary Commodity Price System (PCPS)** — termos de uso do FMI (https://www.imf.org/external/terms.htm), citar a fonte. Ficha: `docs/fontes/fmi-pcps.md`.
- **Banco Mundial - Commodity Markets Outlook, Pink Sheet (dados mensais)** — CC BY 4.0, citar a fonte. Ficha: `docs/fontes/banco-mundial-cmo.md`.
- **IBGE, IPCA** — via marts do projeto (CC BY 4.0, `LICENSE-DADOS.md`).

## Cuidados de leitura

- Café moído é produto industrializado (torra, embalagem, marca) e mistura tipos; os preços internacionais são de café verde exportado. As razões mostram direção e defasagem, não margem.
- O IBGE não publica a composição do café moído entre arábica e robusta; as séries ficam separadas e nenhuma cesta é inventada.
- A conversão usa a PTAX média do mês sobre o preço médio do mês: aproximação do preço diário convertido pelo câmbio do dia, que as fontes não publicam.
- FMI e Banco Mundial publicam a mesma família de cotações; diferenças acima de 1% estão registradas em `reference/excecoes_validacao_cafe.csv`, sem ajuste.
- Possível fonte futura: indicadores CEPEA/Esalq de arábica e robusta (mercado físico brasileiro), se o CEPEA autorizar acesso automatizado (ver o projeto).
