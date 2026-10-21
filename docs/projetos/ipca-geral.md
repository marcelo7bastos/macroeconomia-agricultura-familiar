# Projeto: preparar os dados do IPCA geral

- **Issue de referência:** [#12 — Fonte: IPCA cheio](https://github.com/marcelo7bastos/macroeconomia-agricultura-familiar/issues/12).
- **Situação:** entrega principal implementada e integrada à `main` no PR #58; aceite operacional e revisão humana da harmonização pendentes.
- **Data do levantamento:** 20/10/2026.
- **Plano de tarefas para o GitHub Projects:** [tarefas.json](ipca-geral/tarefas.json).
- **Fonte técnica:** [ficha do IPCA](../indices/ipca.md) e [IBGE/SIDRA](../fontes/ibge-sidra.md).

## Resultado e escopo

Disponibilizar uma base mensal auditável do **IPCA cheio, Brasil (N1)**: índice geral e sua
classificação própria até subitem, incluindo alimentação e bebidas, alimentação no domicílio
e fora do domicílio. O objetivo é preparar os dados para análise e painéis; a criação de um
painel ou de um indicador específico da agricultura familiar é outra entrega.

**Entrega principal:** julho/2006 até o último mês completamente publicado pelo IBGE, com as
POFs 2002-03, 2008-09 e 2017-18. Em 20/10/2026, os metadados consultados terminam em setembro/2026.
O fim da série permanece dinâmico: não fixar setembro no código nem prever meses futuros.

A implementação cobre as três POFs, incluindo janeiro/2020 em diante. O histórico anterior a
julho/2006 é uma extensão explícita, condicionada ao tratamento de tabelas complementares.

O IPCA não substitui o IPCA-15. Ambos coexistem com códigos de índice, saídas e validações
próprios; a base já publicada do IPCA-15 precisa continuar funcionando.

## Cobertura e fontes

| Papel | Tabela SIDRA | Período conferido | Tratamento / situação |
|---|---|---|---|
| Dados detalhados | 7060 | jan/2020–set/2026, aberta | Prova inicial e série corrente |
| Dados detalhados | 1419 | jan/2012–dez/2019 | Retrocarga da entrega principal |
| Dados detalhados | 2938 | jul/2006–dez/2011 | Retrocarga da entrega principal |
| Referência oficial do geral | 1737 | dez/1979–set/2026, aberta | Validar os resultados no intervalo comum |
| Extensão histórica: variação | 655 | ago/1999–jun/2006 | Compor com 656 e 657, após decisão de esquema |
| Extensão histórica: peso | 656 | ago/1999–jun/2006 | Complemento, não sucessora da 655 |
| Extensão histórica: acumulado no ano | 657 | ago/1999–jun/2006 | Complemento, não sucessora da 656 |

Datas, variáveis, categorias e peculiaridades ficam documentadas na ficha. O levantamento de
metadados das tabelas 655/656/657 não equivale à extração nem à validação dessa extensão.

Variáveis do IPCA: `63` → `variacao_mensal`, `69` → `variacao_acum_ano`, `66` → `peso`,
`2265` → `variacao_acum_12m`; na referência, `2266` → `numero_indice`, `2263` →
`variacao_acum_3m` e `2264` → `variacao_acum_6m`, além das variáveis comuns. Confirmar a
presença e a disponibilidade efetiva por tabela e mês, preservando os sinais da fonte.

As trocas de POF do IPCA ocorrem um mês antes das do IPCA-15. Não reaproveitar suas datas,
árvore de categorias ou contagens de exceções. A tabela 7060 tem 377 subitens; a 7062 do
IPCA-15 tem 367, segundo o levantamento do projeto.

## Arquitetura e contratos

```mermaid
flowchart LR
    A[APIs oficiais IBGE] --> B[raw por tabela e mês + manifesto]
    B --> C[Dimensão + fato + referência]
    C --> D[Validações do IPCA]
    D --> E[Mapa próprio de harmonização + série longa]
    E --> F[Indicadores + marts do IPCA]
    F --> G[CSV + metadados + relatórios]
    D -->|falha sem explicação| H[Diagnóstico e correção antes de publicar]
```

Reutilizar catálogo, cliente HTTP, raw, classificação, transformações e indicadores onde o
contrato já é genérico. Alterar código compartilhado apenas diante de uma diferença demonstrada,
com regressão para o IPCA-15. Não duplicar o pipeline inteiro nem criar um agente por índice.

| Camada | Contrato da implementação |
|---|---|
| Catálogo | Entrada `ipca`, tabela, variáveis, período e POF oficiais; campos semânticos iguais aos existentes |
| Raw | `data/raw/ibge_sidra/<tabela>/<AAAAMM>.json.gz`, metadados e manifesto com URL, coleta e SHA-256 |
| Classificação | `data/staging/ipca/dim_classificacao.parquet`; hierarquia pelo código IBGE, nunca pelo campo `nivel` |
| Fato | `data/staging/ipca/fato_ipca.parquet`; chave `(mes, tabela_sidra, codigo_sidra)`, Brasil |
| Referência | `data/staging/ipca/ref_ipca_geral.parquet`; cobertura da 1737 separada da cobertura do detalhe |
| Validação | `data/staging/ipca/validacao.json`; falhas e exceções contadas, sem publicar resultado inválido |
| Harmonização | `reference/map_harmonizacao_ipca.csv`; revisão humana preservada e quebras explícitas |
| Série longa | `data/staging/ipca/serie_longa_ipca.parquet`; não emendar categoria incerta |
| Consumo | `data/marts/ipca_{categorias,mensal,acumulados,contribuicoes,difusao}.csv` e chave `ipca` em `data/metadata.json` |
| Documentação | Páginas `docs/transformacoes/ipca.html` e `docs/revisao/harmonizacao_ipca.html`, com referências corretas ao IPCA |

As saídas de consumo são parte da entrega ponta a ponta, depois da preparação e validação do
staging. Nenhuma saída será declarada pronta apenas porque um comando terminou sem erro.

## Pendências após o PR #58

| Tema | Situação e próximo passo |
|---|---|
| Cobertura da referência | Resolvido: 1737 desde 1979-12 no raw; staging recortado ao detalhe desde jul/2006 |
| Fontes e exceções | Implementado: arquivos próprios, 952 ausências identificadas no raw e anomalias diagnosticadas, A-033 a A-035 |
| Relatórios | Publicados com tabela 1737 e variáveis do IPCA; relatório do IPCA-15 preservado |
| Automação | Seleção de índice e execução serial integradas; conferir primeira execução manual pós-merge no Actions |
| Harmonização | 63 propostas não revisadas continuam como quebras; quatro lacunas impedem emendas automáticas |
| Tabelas complementares anteriores a 2006 | Pendente: modelar composição de 655/656/657 por mês/categoria, sem forjar tabelas sucessivas |
| GitHub Projects | Bloqueado por permissão da integração; cartões e publicador preparados, nenhum quadro criado por esta entrega |

Os módulos `transform.ipca15` e `validate.ipca15` recebem `--indice ipca`; uma renomeação
compatível está apenas proposta em [Estrutura](../ESTRUTURA.md).

## Etapas, dependências e critérios de aceite

| ID | Entrega | Dependências | Aceite principal |
|---|---|---|---|
| IPCA-01 | Descoberta oficial e ficha | — | Metadados, períodos e amostras dos marcos conferidos; cobertura e ausências explícitas |
| IPCA-02 | Catálogo e cobertura da referência | 01 | `ipca` válido no catálogo, sem forjar datas da 1737; testes do IPCA-15 continuam válidos |
| IPCA-03 | Extração incremental e raw auditável | 02 | Retomada, reexecução e revisão sem duplicação; manifesto íntegro e volume de chamadas registrado |
| IPCA-04 | Classificação, fato e referência | 03 | Staging tipado, sem chaves repetidas nem conversão silenciosa de ausentes em zero |
| IPCA-05 | Validações e diagnóstico do IPCA | 04 | Referências oficiais e identidades passam; erros injetados são detectados |
| IPCA-06 | Prova ponta a ponta da série corrente | 05 | 2020+ vai de raw a saída revisada; 2026 contém só meses efetivamente publicados |
| IPCA-07 | Retrocarga até jul/2006 e harmonização | 06 | Três POFs cobertas sem lacunas; continuidades revisadas e quebras preservadas |
| IPCA-08 | Indicadores e contratos de consumo | 07 | Marts, metadados e relatórios consistentes, incluindo alimentos dentro/fora de casa |
| IPCA-09 | Atualização automática e aceite final | 08 | Novo mês, revisão, ausência de novidade e falha da fonte testados sem regressão do IPCA-15 |
| IPCA-10 | Extensão ago/1999–jun/2006 | 09 | Decisão de composição aprovada antes da extração; pesos, variação e acumulado unidos sem duplicação |

As etapas acima preservam o plano de aceite original. Em 20/10/2026, fontes, catálogo, raw,
transformação, validações e saídas estão implementados. IPCA-07 ainda requer revisão humana das
63 propostas; IPCA-09 ainda requer uma execução manual auditada após merge; IPCA-10 não foi
implementada. Implementação não equivale ao aceite integral de todos os cartões.

Evidências do PR #58: 273 testes locais passaram em 119,92 s; outros 54 testes passaram com
recursos avançados da CPU desativados; Ruff e pipeline `--forcar` passaram. São resultados daquela
entrega, não promessa de duração ou resultado de execuções futuras.

### Verificações obrigatórias

- Integridade do raw e dos manifestos, contagens por tabela/mês e ausência de lacunas no recorte.
- Esquema, categorias sem pai, chaves únicas e cinco níveis hierárquicos corretamente derivados.
- Pesos, reconciliação, continuidade, acumulados e índice geral confrontados com o publicado.
- Testes específicos dos marcos jun/2006→jul/2006, dez/2011→jan/2012 e dez/2019→jan/2020,
  conforme a cobertura efetivamente ativada. Sem amostra anterior disponível, declarar o teste
  ainda não executado em vez de tratá-lo como aprovado.
- Nulos e sinais especiais preservados; validações de qualidade não substituídas pela tolerância
  de comparação entre ambientes.
- Na comparação de publicações: diferença absoluta máxima inclusiva de **0,001 p.p.** apenas
  para acumulados calculados e contribuições; oficiais, códigos, datas, textos, estrutura e
  ausentes exatos. Cada hash confere com seu próprio CSV (A-031).
- Meses sem novidade não alteram arquivos; revisões ficam auditáveis; falha bloqueia a publicação
  do índice afetado. Recuperação após falha testada com procedimento documentado.
- `uv run ruff check .`, `uv run ruff format --check .` e suíte relevante, sem zerar ou pular
  verificações do IPCA-15 para incluir o IPCA.
- Revisão metodológica antes de cada PR e validação de dados antes de publicar marts.

## Organização do GitHub Projects

**Título:** IPCA geral — preparação dos dados.

A issue #12 permanece como referência da frente. Criar dez issues de trabalho com os IDs acima,
inseri-las no projeto e vincular o projeto ao repositório. Os corpos dos cartões contêm escopo,
dependências, critérios de aceite e referência à #12. O publicador conserva a situação inicial `backlog` dos cartões originais; ele não sincroniza
conclusões com o código. Antes de aplicá-lo agora, revisar o escopo e os estados à luz das
entregas acima para não apresentar trabalho implementado como novo.

Usar a visualização Board agrupada por **Status** (A fazer / Em andamento / Concluído, ou os
nomes equivalentes da conta). Bloqueios e revisão ficam registrados nos cartões até a equipe
optar por ampliar os estados. Manter IPCA-10 separado da definição de pronto da entrega principal.

O publicador [publicar.py](ipca-geral/publicar.py) começa em modo de simulação, não armazena
credenciais e reutiliza projeto e issues pelos identificadores, sem criar duplicatas em uma
retomada. A API e as permissões de Projects precisam funcionar antes de aplicá-lo:

```bash
python docs/projetos/ipca-geral/publicar.py
python docs/projetos/ipca-geral/publicar.py --aplicar
```

O publicador reutiliza a autenticação do `gh`. Se houver uma credencial específica
`GH_PROJECTS_TOKEN`, usa-a somente no processo filho do CLI, sem salvar ou imprimir seu valor.
Ela precisa autorizar leitura/escrita em Projects e Issues do repositório. Cadastre valores
somente nas configurações seguras do ambiente; nunca no JSON, nos arquivos ou no chat. A
integração GitHub que permite clonar e fazer push não garante permissão de Projects.

O publicador cria os itens e o vínculo ao repositório. A seleção de layout Board e o agrupamento
por Status são ajustes de apresentação feitos na interface do GitHub Projects; não se confundem
com a criação dos itens. No caso de falta de acesso, preservar o plano e os cartões preparados,
registrar o bloqueio e retomar a publicação sem recriar o que já existe.

## Implementação e limites

A entrega principal foi extraída, transformada e validada: 805 respostas mensais oficiais,
243 meses de detalhe e 111.299 observações, de julho/2006 a setembro/2026. Os cinco marts e seu
dicionário estão em `data/marts/ipca_*`; a explicação auditável está em
[transformações do IPCA](../transformacoes/ipca.html). As saídas do IPCA-15 foram preservadas.

As 63 propostas de harmonização pendentes continuam marcadas como quebras até revisão humana.
A configuração da atualização dos dois índices já está na `main`; o aceite operacional exige
a primeira execução manual conferida no GitHub Actions. A publicação do quadro no GitHub Projects continua bloqueada pela permissão da
integração; o plano e os cartões estão preparados para retomada, sem bloquear o pipeline.

A extensão anterior a julho/2006 (IPCA-10) permanece separada. A entrega não inclui recortes
regionais, INPC, IPCA-E, dessazonalização, previsões, painel ou definição de uma cesta da
agricultura familiar. Esses temas exigem escopo e critérios próprios.
