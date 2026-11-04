# Banco Mundial: Pink Sheet (Commodity Markets)

- **Instituição:** Banco Mundial (Prospects Group)
- **Última conferência:** 2026-11-04 (piloto do café, #62)
- **Licença:** CC BY 4.0, conforme o catálogo de dados do Banco Mundial. **Pendência:** confirmar
  na página do conjunto de dados antes de integrar o PR.

## Séries usadas

| Coluna da aba `Monthly Prices` | Descrição da fonte (aba `Description`) | Unidade | Desde |
|---|---|---|---|
| `Coffee, Arabica` | ICO indicator price, other mild Arabicas, average New York and Bremen/Hamburg markets, ex-dock | US$/kg | 1960-01 |
| `Coffee, Robusta` | ICO indicator price, Robustas, average New York and Le Havre/Marseilles markets, ex-dock | US$/kg | 1960-01 |

Valores com **duas casas decimais**. São a mesma família de cotações do FMI (indicadores da
Organização Internacional do Café), por isso um confere o outro.

## Endpoints

- Página: <https://www.worldbank.org/en/research/commodity-markets>
- Planilha: `https://thedocs.worldbank.org/en/doc/<hash>-<edição>/related/CMO-Historical-Data-Monthly.xlsx`.
  **O endereço muda a cada edição** (em 2026-11-04: `74e8be41ceb20fa0da750cda2f6b9e4e-0050012026`).
  O extrator lê a página e exige exatamente um link com esse nome de arquivo; não fixa a URL.

## Formato e valores especiais

- Aba `Monthly Prices`: quatro linhas de título (a quarta é `Updated on <data>`), uma de nomes,
  uma de unidades (`($/kg)`) e depois uma linha por mês com período `AAAAMNN` (ex.: `2026M10`).
- A planilha traz uma aba `Mismatch Details` com as diferenças em relação à edição anterior
  (revisões). Em nov/2026 ela não lista café.
- O Banco Mundial publica o mês no início do mês seguinte (em 2026-11-04, ia até out/2026, um mês
  a mais que o FMI).
- **O raw guarda um recorte**, não a planilha: CSV com `mes, codigo, unidade, valor` das colunas
  de café, com o SHA-256 e a URL da planilha original no manifesto. A planilha tem ~600 kB e muda
  todo mês; o recorte preserva os valores exatos que o projeto usa.

## Diferença em relação ao FMI

Depois de converter US¢/lb para US$/kg, FMI e Banco Mundial diferem menos de 1% em quase todos os
meses desde jul/2006 (mediana 0,07% no arábica e 0,13% no robusta). Quatro meses passam de 1% e
ficam registrados como exceções contadas em `reference/excecoes_validacao_cafe.csv`; não há ajuste.

## Falhas conhecidas e como tratar

- Nenhum ou mais de um link para a planilha na página: o extrator falha.
- Coluna, unidade ou período fora do formato: o leitor falha, sem adivinhar.

## Acesso a partir dos ambientes

- Sessão na nuvem: exige `www.worldbank.org` e `thedocs.worldbank.org`.
- GitHub Actions: sem restrição conhecida; `robots.txt` permite `User-agent: *`.
