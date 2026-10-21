# IBGE: SIDRA e API de agregados

- **Instituição:** Instituto Brasileiro de Geografia e Estatística
- **Última revisão da ficha:** 2026-10-20 (IPCA e IPCA-15; datas das consultas específicas abaixo)

## Endpoints

| Uso | URL |
|---|---|
| Metadados de uma tabela (variáveis, classificações, período) | `https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados` |
| Períodos disponíveis | `https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/periodos` |
| Valores | `https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all/v/{variaveis}/p/{periodos}/c315/{categorias}` |

Sintaxe de períodos aceita em `/values`: `p/all`, `p/AAAAMM`, faixa `p/AAAAMM-AAAAMM` (ex.:
`p/200005-200208`). Categorias: `c315/all` ou lista de ids (`c315/7169,7170`).

## Limites e paginação

Medido em 2026-10-19 (#3):

- **Limite: 50.000 valores por requisição.** A API calcula o pedido como o produto cartesiano
  `variáveis × períodos × categorias × unidades territoriais` dos metadados (não conta só o que
  existe) e recusa antes de consultar.
- **Ao ultrapassar:** HTTP **400**, `content-type: text/plain`, corpo
  `Quantidade de valores solicitados: 133425 excedeu o limite: 50000` (1646 inteira:
  3 × 75 × 593). Não é JSON; o cliente precisa tratar 400 como erro de paginação, não retentar.
- Conferido na borda: 1646 v/all, 28 períodos, c315/all = 49.812 valores → 200 (15,3 MB, ~4 s);
  29 períodos = 51.591 → 400 com a mesma mensagem.
- Cada valor ocupa ~300 bytes de JSON; 50 mil valores ≈ 15 MB.
- **Como o extrator respeita o limite:** uma requisição por tabela × mês, com todas as variáveis
  e categorias (decisão 0003). Exemplos: 1646, 3 × 593 = 1.779 valores; 7062,
  4 × 447 = 1.788; 1419, 4 × 464 = 1.856. O extrator confere que a resposta tem exatamente variáveis × categorias
  registros.

## Formato e valores especiais

- **Metadados:** `periodicidade` = `{"frequencia": "mensal", "inicio": 200005, "fim": 200607}`,
  com `inicio`/`fim` **inteiros** AAAAMM. `/periodos` devolve lista de
  `{"id": "200005", "literals": ["maio 2000", "maio de 2000"], "modificacao": "15/07/2011"}`, com
  `id` **texto** AAAAMM e `modificacao` em DD/MM/AAAA (data da última alteração do período).
- **Valores (`/values`, JSON padrão):** lista em que o **primeiro elemento é o cabeçalho**
  (descrição das colunas) e os demais são as linhas. Todos os campos são texto. Colunas para
  `t/{tabela}/n1/all/v/.../p/.../c315/...`:
  `NC`, `NN` (nível territorial), `MC`, `MN` (unidade de medida: `%`, ou vazio quando `V` é `...`),
  `V` (valor), `D1C`/`D1N` (Brasil), `D2C`/`D2N` (variável), `D3C`/`D3N` (mês: `200005` /
  `maio 2000`), `D4C`/`D4N` (categoria da 315: id da API / nome com código, ex.
  `1101002.Arroz`). A ordem das dimensões segue a ordem da URL.
- `V` usa ponto decimal e casas fixas: variações com 2 casas, peso (357) com 4.
- A classificação aparece com o código IBGE no nome da categoria (`<código>.<nome>`, sem espaço;
  o geral é `Índice geral`, sem código); é desse código que sai a hierarquia, não do campo `nivel`
  (A-001).
- **Valores especiais e tratamento vigente (A-009, A-033):** `...` é indisponível e vira
  ausente; `-` é zero absoluto e vira 0,0. O literal original continua preservado no raw.
  A [ajuda oficial do SIDRA](https://apisidra.ibge.gov.br/home/ajuda) confirma os sinais; a carga
  do IPCA encontrou 13 `-` em 2265 na 1419. Esses zeros também passam pelas validações (A-035).
  `X`, `..`, vazio e qualquer outro texto não numérico interrompem a transformação; não são
  convertidos silenciosamente em nulos. A sugestão exploratória de aceitar todos como nulos
  foi superada pelo tratamento implementado e testado.
- **Tabela de referência sem classificação:** a 3065 (IPCA-15) e a 1737 (IPCA) usam URL sem
  `/c315/...`; a classificação e a contagem de registros do detalhe não se aplicam a elas.

## Falhas conhecidas e como tratar

- Retentativas com espera exponencial e timeout explícito (`PLANEJAMENTO.md`, 3.2).
- Detecção de mês novo pelos metadados (`periodicidade.fim`) antes de baixar valores. Em
  2026-10-19 o `fim` da 7062 e da 3065 era 202609 (modificação 25/09/2026).
- HTTP 400 em `/values` com corpo texto "excedeu o limite" é erro de paginação: não retentar.

## Acesso a partir dos ambientes

- **Sessão do Claude Code na nuvem:** em 2026-10-19 a política de rede do ambiente bloqueava os dois
  domínios (403 no proxy). É preciso incluir `servicodados.ibge.gov.br` e `apisidra.ibge.gov.br` em
  *Allowed domains* nas configurações do ambiente (A-004). Depois de liberados, no mesmo dia, as
  duas APIs responderam normalmente pelo proxy (apisidra atrás do Cloudflare).
- **Documentação do IBGE na sessão na nuvem:** `ftp.ibge.gov.br`, `www.ibge.gov.br`,
  `biblioteca.ibge.gov.br` e `agenciadenoticias.ibge.gov.br` continuavam bloqueados em 2026-10-19
  (A-004).
- **GitHub Actions:** testado pelo workflow `API do IBGE` (`.github/workflows/api-ibge.yml`) no PR da #3; resultado registrado no PR.
