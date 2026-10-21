# Estrutura do repositório e proposta de organização

Revisão de 21/10/2026, [issue #59](https://github.com/marcelo7bastos/macroeconomia-agricultura-familiar/issues/59).
Os guias de navegação foram adicionados nesta revisão. As migrações de caminhos abaixo são
**propostas para discussão**; nenhum arquivo de dados ou módulo foi movido.

## Organização atual

```text
config/series.yaml             catálogo de fontes, índices, tabelas e variáveis
src/macroaf/                  pipeline compartilhado por etapas
  extract/                    cliente, metadados, extração e armazenamento raw
  transform/                  classificação, fato, referência e harmonização
  indicators/                 índice, acumulados, contribuições, difusão e sazonalidade
  validate/                   contratos e validações dos dados
  marts/                      publicação e dicionários
  relatorios/                 coleta de fatos, gráficos e geração dos HTMLs
data/                         raw, staging, marts e metadados da publicação
reference/                    mapas, exceções, limites, diagnósticos e histórico de séries
tests/                        testes compartilhados e testes de cada índice
docs/                         guias, metodologia, planejamento, fichas e histórico de decisões
  indices/ e fontes/          conhecimento das séries e APIs
  gestao/                     explicações e exploração para gestores
  transformacoes/ e revisao/   relatórios HTML técnicos gerados
  projetos/                   planos e apoio ao acompanhamento de entregas
.claude/                      agentes, skills e hook de preparação
.github/workflows/            CI, acesso ao IBGE e atualização de dados
```

## Separar `data/` por indicador?

Recomenda-se **camada primeiro e índice dentro da camada quando necessário**. Aqui, IPCA e
IPCA-15 são índices; acumulados, contribuições e difusão são produtos calculados desses índices.
Criar uma pasta de topo para cada produto fragmentaria a proveniência e duplicaria classificações.

| Parte | Recomendação | Motivo |
|---|---|---|
| `raw/<fonte>/<tabela>/` | Manter | A tabela identifica o objeto oficial; permite compartilhar fontes sem duplicar respostas |
| `staging/<indice>/` | Manter e documentar | Já separa o processamento descartável por índice |
| `marts/<indice>_*.csv` | Manter nesta etapa | Prefixos distinguem índices e preservam URLs estáveis usadas pelo Power BI |
| `data/metadata.json` | Manter por enquanto | Uma chave por índice já separa as publicações; dividir exige alterar o publicador e consumidores |
| `reference/*.csv` | Propor `reference/<indice>/` | Crescimento por índice justifica agrupar regras e decisões, sem tratar referências como cache |

Para um futuro catálogo com muitos índices, considerar `data/marts/<indice>/` e
`data/metadata/<indice>.json`. A mudança só compensa quando o volume dificultar a navegação ou
quando houver consumidores que precisem de publicações independentes. Não criar cópias manuais
nos dois lugares: elas podem divergir e duplicam o volume versionado.

## Melhorias nas demais pastas

| Prioridade | Proposta | Efeito e condição |
|---|---|---|
| Agora | Guias `docs/README.md`, `data/README.md`, `reference/README.md`, operação e esta estrutura | Navegação e responsabilidades claras, sem migração de contratos |
| Próxima etapa | Agrupar `reference/<indice>/{map_harmonizacao,excecoes_validacao,limites_validacao,historico_series}.csv` | Migrar todos os leitores, gravadores, testes e links juntos; preservar decisões e histórico |
| Próxima etapa | Mover `docs/projetos/ipca-geral/publicar.py` para `scripts/projetos/` | Separar código operacional de documentação; adaptar caminho do JSON, testes e comandos |
| Próxima etapa | Renomear os módulos genéricos `transform/ipca15.py` e `validate/ipca15.py` | Nome refletirá seu uso pelos dois índices; manter módulos antigos como encaminhadores dos comandos/imports |
| Conforme crescer | Agrupar testes em `tests/unitarios/`, `tests/integracao/` e `tests/contratos/` | Migrar imports de `comparar_publicacao.py`, fixtures e comandos do CI juntos; hoje o volume ainda é administrável |
| Conforme crescer | Separar relatórios gerados de uma futura árvore do site | O Pages desta entrega serve HTML estático; site Quarto continua separado na issue #18 |
| Conforme medir | Reduzir crescimento do Git com armazenamento externo de raw ou Git LFS | Medir tamanho e tempo de clone antes; preservar verificações e disponibilidade para CI e consumidores |

O código deve continuar organizado por **etapa e função**, com configuração por índice.
Pastas `src/ipca/` e `src/ipca15/` com pipelines duplicados aumentariam o custo de correção.
`reference/` fica separado do dado bruto porque reúne decisões e evidências que não são
recriadas apenas baixando novamente a API.

## Critérios de uma futura migração

1. Inventariar consumidores e URLs, incluindo Power BI, HTML, workflows, scripts e testes.
2. Registrar a decisão arquitetural e o contrato de compatibilidade em PR próprio.
3. Centralizar resolução de caminhos antes de mudar os arquivos; mover com histórico do Git.
4. Migrar leituras, gravações e links no mesmo PR; preservar SHA-256 dos conteúdos movidos.
5. Reproduzir marts dos dois índices sem alterar valores, chaves, revisões ou decisões.
6. Validar links, comandos antigos e novos e uma execução de cada índice. Publicação em paths
   novos exige plano explícito para consumidores antigos; GitHub raw não oferece redirecionamento
   automático confiável para arquivos movidos.
7. Atualizar os guias e retirar compatibilidade apenas após migração dos consumidores.

Nenhuma migração deve ser justificada apenas por estética. A primeira necessidade técnica é
reduzir caminhos espalhados no código e preservar os contratos públicos; a estrutura física vem depois.
