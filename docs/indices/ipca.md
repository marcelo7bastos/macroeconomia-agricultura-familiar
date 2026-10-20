# IPCA

- **Fonte:** IBGE, SIDRA ([ficha da fonte](../fontes/ibge-sidra.md)).
- **Situação no projeto:** planejamento da [issue #12](https://github.com/marcelo7bastos/macroeconomia-agricultura-familiar/issues/12); extração histórica e transformação ainda não implementadas para este índice.
- **Última conferência dos metadados:** 2026-10-20, nas APIs oficiais de metadados, períodos e pequenas amostras de valores.
- **Recorte territorial inicial:** Brasil (`N1`). A existência de outros níveis territoriais nas tabelas não os inclui nesta entrega.

## O que mede

O Índice Nacional de Preços ao Consumidor Amplo (IPCA) acompanha a variação dos preços ao consumidor segundo a população-alvo e o período de coleta definidos pelo IBGE. É um índice distinto do IPCA-15; não se deve preencher um com observações do outro.

Neste projeto, **IPCA geral** significa preparar o índice completo: índice geral, grupos, subgrupos, itens e subitens, incluindo alimentação. A referência histórica somente do índice geral é uma camada separada e não substitui o detalhe por categoria.

## Tabelas da entrega principal

A primeira prova de ponta a ponta pode usar a estrutura atual, de janeiro/2020 em diante. A entrega principal estende o detalhe a julho/2006, com três tabelas de dados consecutivas. As datas abaixo foram verificadas nos campos `periodicidade` e nas listas de períodos; as listas de cada tabela não têm lacunas internas.

| Tabela | Papel | Período verificado | Meses em 20/10/2026 | Variáveis |
|---|---|---|---:|---|
| [2938](https://sidra.ibge.gov.br/tabela/2938) | Dados | jul/2006–dez/2011 | 66 | 63, 69, 66 |
| [1419](https://sidra.ibge.gov.br/tabela/1419) | Dados | jan/2012–dez/2019 | 96 | 63, 69, 2265, 66 |
| [7060](https://sidra.ibge.gov.br/tabela/7060) | Dados, aberta | jan/2020–set/2026 | 81 | 63, 69, 2265, 66 |
| [1737](https://sidra.ibge.gov.br/tabela/1737) | Referência oficial do geral, aberta | dez/1979–set/2026 | 562 | 2266, 63, 2263, 2264, 69, 2265 |

As três tabelas de detalhe se sucedem sem sobreposição nem lacuna: `2006-07 → 2011-12`, `2012-01 → 2019-12`, `2020-01 → último período publicado`. As transições associadas às estruturas de pesos de POF 2002-03, 2008-09 e 2017-18 não são as mesmas datas do IPCA-15. O nome e o intervalo oficial de cada tabela precisam prevalecer sobre qualquer reaproveitamento de configuração do piloto.

Os metadados das tabelas de detalhe oferecem `N1`, `N6` e `N7`; a 1737 oferece somente `N1`. A 1737 não tem classificação 315.

### Variáveis e nomes internos propostos

| Id | Nome oficial | Unidade | Nome interno já usado no piloto |
|---|---|---|---|
| 63 | IPCA - Variação mensal | % | `variacao_mensal` |
| 69 | IPCA - Variação acumulada no ano | % | `variacao_acum_ano` |
| 66 | IPCA - Peso mensal | % | `peso` |
| 2265 | IPCA - Variação acumulada em 12 meses | % | `variacao_acum_12m` |
| 2266 | IPCA - Número-índice (base: dezembro de 1993 = 100) | Número-índice | `numero_indice` |
| 2263 | IPCA - Variação acumulada em 3 meses | % | `variacao_acum_3m` |
| 2264 | IPCA - Variação acumulada em 6 meses | % | `variacao_acum_6m` |

Estes ids são do IPCA; os ids 355, 356, 357 e 1117–1120 do IPCA-15 não podem ser copiados para seu catálogo. O id de variável 63 também **não é uma indicação para coletar a tabela 63**: os metadados da tabela 63 descrevem pessoal ocupado na indústria, sem relação com este índice.

## Classificação e alimentação

As tabelas 2938, 1419 e 7060 usam a classificação **315 — Geral, grupo, subgrupo, item e subitem**. As contagens foram derivadas do código no nome da categoria (`<código>.<nome>`), nunca do campo `nivel`.

| Tabela | Geral | Grupos (1 dígito) | Subgrupos (2) | Itens (4) | Subitens (7) | Total |
|---|---:|---:|---:|---:|---:|---:|
| 2938 | 1 | 9 | 19 | 52 | 384 | 465 |
| 1419 | 1 | 9 | 19 | 52 | 383 | 464 |
| 7060 | 1 | 9 | 19 | 51 | 377 | 457 |

Nessas três tabelas, não foram encontrados códigos IBGE duplicados ou categorias órfãs: os pais derivados pelo código existem na mesma tabela. O geral aparece sem prefixo numérico (`Índice geral`, id SIDRA 7169), devendo receber a convenção interna `codigo_ibge = "0"`.

O recorte de alimentação acompanha a própria árvore do IPCA:

- `1`: Alimentação e bebidas;
- `11`: Alimentação no domicílio;
- `12`: Alimentação fora do domicílio;
- itens e subitens descendentes destes códigos, conservando a identidade publicada por tabela e id SIDRA.

A 7060 contém 377 subitens, enquanto a 7062 do IPCA-15 contém 367. Não usar a dimensão nem o mapa de harmonização do IPCA-15 para preencher categorias do IPCA. O mapa próprio do IPCA deve registrar continuidades e quebras entre 2938, 1419 e 7060; até haver prova ou revisão de uma correspondência, preservar a quebra.

## Referência oficial para validação

A tabela **1737** confere, para o índice geral, variação mensal (63), acumulados no ano (69), em 3/6/12 meses (2263/2264/2265) e número-índice (2266).

A referência começa em dezembro/1979; o detalhe da entrega principal começa em julho/2006. O planejamento deve separar explicitamente a cobertura da referência da cobertura do fato detalhado. Ao validar ou publicar, alinhar os períodos aplicáveis e documentar a janela anterior necessária para cada acumulado: a existência de 562 meses na referência não significa que existam categorias e pesos nesse mesmo intervalo. Uma consulta ou extração mais longa da referência não deve criar linhas artificiais no fato por categoria.

Pesos dos grupos e filhos, reconciliação pai/filhos, continuidade, acumulados e costuras devem ser validados com os dados do próprio IPCA. Não copiar limites empíricos nem exceções contadas do IPCA-15: qualquer diferença além do limite metodológico exige diagnóstico e registro próprios. A tolerância entre publicações de ambientes distintos (A-031) é separada dessas validações contra o IBGE.

## Valores ausentes e amostras verificadas

A existência da variável 2265 nos metadados não garante valor disponível em todo mês. Nas consultas de todos os períodos para **geral (7169) e arroz (7173)**:

| Tabela | Meses com `...` para 2265 nas duas categorias amostradas | Primeiro valor presente |
|---|---|---|
| 1419 | jan/2012–nov/2012 | dez/2012 |
| 7060 | jan/2020–nov/2020 | dez/2020 |

Esse levantamento identifica uma peculiaridade real, mas não certifica a disponibilidade de todas as categorias; o perfil completo de ausências pertence à etapa de extração/validação. `...` permanece ausente no campo oficial, sem virar zero. Onde for necessário calcular acumulados, conservar a distinção entre valor oficial e calculado e conferir a composição contra a referência.

Amostras também confirmaram, no mês inicial de cada estrutura, os registros do geral e do arroz para as variáveis disponíveis. Na referência 1737, setembro/2026 retornou variação mensal de **0,82%**, acumulado no ano de **3,95%** e em 12 meses de **4,58%**. São valores observados nesta consulta, sem projeção para meses seguintes.

## Extensão histórica separada: agosto/1999–junho/2006

Os metadados e períodos das tabelas abaixo foram conferidos. Cada uma possui 83 meses contínuos, classificação 315 e 593 categorias (1 geral, 9 grupos, 19 subgrupos, 52 itens e 512 subitens). Seus pares de id SIDRA/nome são idênticos na consulta de 20/10/2026.

| Tabela | Variável publicada | Cobertura |
|---|---|---|
| [655](https://sidra.ibge.gov.br/tabela/655) | 63 — variação mensal | ago/1999–jun/2006 |
| [656](https://sidra.ibge.gov.br/tabela/656) | 66 — peso mensal | ago/1999–jun/2006 |
| [657](https://sidra.ibge.gov.br/tabela/657) | 69 — acumulado no ano | ago/1999–jun/2006 |

As três tabelas são **complementares no mesmo período**, não estruturas de pesos consecutivas. A 655 sozinha não prepara o mesmo fato do piloto: faltariam peso e acumulado oficial no ano. Antes de incluí-las, projetar a composição por período e categoria com proveniência de cada tabela, validar as chaves de junção e decidir explicitamente a identidade publicada da camada composta.

O catálogo atual exige tabelas de dados em sucessão sem sobreposição. Portanto essa extensão exige desenho de configuração/transformação e testes específicos; não cabe acrescentar as três como tabelas de dados consecutivas nem sobrescrever silenciosamente os ids das fontes. O intervalo ago/1999–jun/2006 fica fora da entrega principal até essa etapa própria. O detalhe anterior a agosto/1999 não foi levantado nesta ficha.

## Endpoints e evidências reproduzíveis

Todos os endpoints a seguir foram consultados em 20/10/2026. As respostas usadas na exploração ficaram em arquivos temporários da sessão; ainda não constituem uma camada raw versionada.

- Metadados: `https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados`.
- Períodos: `https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/periodos`.
- Tabelas conferidas: `2938`, `1419`, `7060`, `1737`, `655`, `656`, `657`; a tabela `63` foi consultada apenas para descartar a confusão com o id da variável.
- Amostra do detalhe: `https://apisidra.ibge.gov.br/values/t/7060/n1/all/v/all/p/202001/c315/7169,7173` (mesmo formato para 2938 em 200607 e 1419 em 201201).
- Perfil amostral de 12 meses: `https://apisidra.ibge.gov.br/values/t/1419/n1/all/v/2265/p/all/c315/7169,7173` e o mesmo caminho para a tabela 7060.
- Referência: `https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/all/p/202609`.
- Amostras legadas: `/values/t/655/n1/all/v/63/p/199908/c315/7169,7173`, `/values/t/656/n1/all/v/66/p/199908/c315/7169,7173` e `/values/t/657/n1/all/v/69/p/199908/c315/7169,7173`, no domínio `apisidra.ibge.gov.br`.

A extração futura deve continuar incremental, com uma requisição por tabela × mês, verificando contagens, preservando resposta oficial e revisão, e respeitando o limite de 50.000 valores do SIDRA já documentado na ficha da fonte. As amostras desta ficha não substituem os testes de dados históricos nem autorizam publicar séries ainda não validadas.
