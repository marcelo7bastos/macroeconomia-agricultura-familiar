# FMI: Primary Commodity Price System (PCPS)

- **Instituição:** Fundo Monetário Internacional (Research Department)
- **Última conferência:** 2026-11-04 (piloto do café, #62)
- **Licença:** a resposta declara `© International Monetary Fund Copyright. All Rights Reserved.`
  e remete aos termos em <https://www.imf.org/external/terms.htm>. **Pendência:** os termos não
  foram lidos (o domínio `www.imf.org` estava bloqueado na sessão). Confirmar se permitem
  republicar os valores num repositório público antes de integrar o PR.
- **Citação sugerida pela fonte:** "International Monetary Fund. Primary Commodity Price System
  (PCPS), https://data.imf.org/en/datasets//IMF.RES:PCPS. Accessed on [data]."

## Séries usadas

| Indicador | Conteúdo | Unidade | Desde |
|---|---|---|---|
| `PCOFFOTM` | Coffee, Other Mild Arabica | US¢/libra-peso | 1992-01 |
| `PCOFFROB` | Coffee, Robustas | US¢/libra-peso | 1992-01 |

Outros indicadores de café no PCPS, não usados: `PCOFF` (índice de café, 2016=100) e
`PCOFFAVG` (média de arábica e robusta). Dimensões da chave:
`COUNTRY.INDICATOR.DATA_TRANSFORMATION.FREQUENCY`, com `COUNTRY=G001` (mundo) e `FREQUENCY=M`.

Transformações pedidas: `USD` (preço) e `INDEX_PCH` (variação mensal %, publicada pelo FMI). A
`INDEX_PCH` serve de **referência oficial**: a variação calculada do preço reproduz a publicada
com diferença de 1e-13 (conferido em 2026-11-04, toda a série).

As médias mensais são calculadas pelo FMI a partir de cotações diárias ou semanais
(documentação técnica do PCPS, jan/2019).

## Endpoints

`https://api.imf.org/external/sdmx/2.1/data/IMF.RES,PCPS/G001.PCOFFOTM+PCOFFROB.USD+INDEX_PCH.M`

- Resposta: SDMX-ML 2.1 *structure specific* (XML), ~240 kB para a série inteira.
- Estrutura do fluxo: `https://api.imf.org/external/sdmx/3.0/structure/dataflow/IMF.RES/PCPS/+?references=all`.
- A API antiga (`dataservices.imf.org`) não responde (502 no proxy da sessão, 2026-11-04).
- A consulta SDMX 3.0 de dados com filtro `c[TIME_PERIOD]` devolveu 400; a 2.1 funciona.

## Formato e valores especiais

- `TIME_PERIOD` no formato `AAAA-MNN` (ex.: `2026-M09`).
- O cabeçalho (`message:Prepared`) muda a cada consulta: o raw compara as **observações**, não os
  bytes, para decidir se há revisão.
- O FMI publica o mês no início do mês seguinte (em 2026-11-04, a série ia até set/2026).

## Falhas conhecidas e como tratar

- Indicador ausente na resposta: o extrator falha.
- Série com `COUNTRY`, `FREQUENCY` ou `SCALE` diferentes do esperado: o leitor falha.

## Acesso a partir dos ambientes

- Sessão na nuvem: exige `api.imf.org`.
- GitHub Actions: sem restrição conhecida; `robots.txt` de `api.imf.org` não tem regras.
