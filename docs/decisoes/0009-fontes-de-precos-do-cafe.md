# 0009. Fontes de preços fora do IBGE no piloto do café

- **Situação:** proposta (aguarda revisão do mantenedor no PR)
- **Data:** 2026-11-04
- **Issue/PR:** #62

## Contexto

O piloto do café compara o café moído do IPCA com o preço do café no mercado. O IBGE não publica
preço de café ao produtor nem cotação internacional em frequência mensal. As regras do projeto
dizem "fontes só por API oficial ou CSV versionado em `reference/`; nada de links de planilhas" e
listam como APIs usadas só as do IBGE.

Fontes avaliadas em 2026-11-04:

- **CEPEA/Esalq** (arábica e robusta, diários, R$/saca): sem API; `robots.txt` bloqueia agentes e
  crawlers, inclusive os da Anthropic; páginas de série respondem 403 a acesso automatizado;
  licença CC BY-NC 4.0. O mantenedor recusou o download manual por ser inviável de manter.
- **Conab** (preços recebidos pelo produtor): o portal de dados responde com certificado TLS de
  outro domínio (`www.conab.gov.br`) e o site institucional redireciona para `www.gov.br`, fora
  da rede da sessão. Sem verificação de TLS não há coleta.
- **FMI, PCPS** (API SDMX), **Banco Mundial, Pink Sheet** (planilha em página pública) e
  **Banco Central, SGS** (API): acessíveis, automatizáveis, com séries mensais desde antes de 2006.

## Decisão

1. **Fontes do piloto:** FMI (`PCOFFOTM`, `PCOFFROB`), Banco Mundial (`Coffee, Arabica`,
   `Coffee, Robusta`) e BCB (PTAX venda diária, série 1, e média mensal, série 3698). Ficam em
   `config/precos.yaml`, separado de `config/series.yaml`, porque não são índices SIDRA com
   tabelas que se sucedem por POF.
2. **Conversão pelo câmbio do período da informação:** as fontes publicam médias mensais, então
   o câmbio é a **média mensal oficial** da PTAX venda (SGS 3698). A média calculada dos dias
   úteis da série diária (SGS 1) não entra no mart: só valida a oficial (dado oficial primeiro).
   Mês sem média oficial ainda publicada fica sem preço em reais até ela sair.
3. **Raw com o mesmo contrato do SIDRA** (decisão 0003): arquivo exato, compactado, imutável, com
   revisões e manifesto; nova camada `extract/raw_arquivos.py` com chaves livres. Exceção: do
   Banco Mundial guarda-se o recorte das colunas de café em CSV, com URL e SHA-256 da planilha
   no manifesto, em vez da planilha inteira (~600 kB que mudam todo mês).
4. **FMI e Banco Mundial ficam ambos** porque publicam a mesma família de cotações (OIC): um
   confere o outro, com limite de 1% e exceções contadas em `reference/excecoes_validacao_cafe.csv`.
5. **IPCA lido dos marts**, sem recálculo; o mart do café roda depois da atualização dos índices.
6. **CEPEA e Conab ficam como fontes futuras**, condicionadas a acesso automatizado autorizado
   (CEPEA) ou a certificado TLS válido e rede liberada (Conab).
7. **Regra do `AGENTS.md`:** a lista de APIs usadas passa a incluir `api.bcb.gov.br`,
   `api.imf.org`, `www.worldbank.org` e `thedocs.worldbank.org`, e a regra "nada de links de
   planilhas" ganha **uma** exceção explícita: a planilha do Pink Sheet, achada pela página oficial
   a cada coleta (nunca por link fixo) e recortada para o raw com o SHA-256 dela no manifesto.
8. **Acumulado em 12 meses do IPCA:** o mart repete o oficial onde o IBGE publica e só calcula
   onde não há publicação, com a coluna `origem_acum_12m`.

## Alternativas consideradas

- **CEPEA por download manual:** recusado pelo mantenedor (inviável de manter).
- **CEPEA por script local:** contraria o `robots.txt` e o bloqueio do site; frágil.
- **Só uma fonte internacional:** perde a conferência cruzada; a divergência FMI × Banco Mundial
  é informação (ver as exceções).
- **Conversão pela PTAX do último dia do mês:** não corresponde a um preço que é média do mês.
- **Converter pela média calculada da PTAX diária:** é a mesma conta sem o arredondamento a quatro
  casas (diferença máxima 0,00005), mas o BCB publica a média; pela regra, usa-se a oficial.
- **Estender `config/series.yaml`:** o esquema e as validações do catálogo pressupõem tabelas
  SIDRA; misturar as duas coisas complica os dois.

## Consequências

- O pipeline passa a depender de três instituições além do IBGE; cada uma tem ficha em
  `docs/fontes/` e falha com mensagem clara quando o formato muda.
- **Pendências de licença antes de integrar (decisão do mantenedor):** os termos do FMI declaram
  "All Rights Reserved" e remetem a <https://www.imf.org/external/terms.htm>, que não pôde ser lido
  na sessão (domínio bloqueado). Os termos gerais do site do Banco Mundial remetem os conjuntos do
  Data Catalog a termos próprios, e `datacatalog.worldbank.org` também estava bloqueado. O
  `LICENSE-DADOS.md` já separa esses valores da CC BY 4.0 do projeto. Se algum termo não permitir
  redistribuir, as séries daquela fonte saem do mart público e ficam só como validação.
- **Auditoria do Banco Mundial:** como a planilha não é guardada e a URL muda a cada edição, o
  SHA-256 registrado no manifesto não pode ser reconferido depois; o recorte guardado é a evidência.
- O preço internacional não é o preço ao produtor brasileiro. Reavaliar quando CEPEA ou Conab
  ficarem acessíveis.
