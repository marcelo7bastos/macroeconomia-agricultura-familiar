# Changelog

Mudanças relevantes do projeto. Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## Não publicado

### Alterado

- Teste de publicação compara acumulados calculados e contribuições com diferença absoluta
  máxima de 0,001 p.p., preservando igualdade exata dos oficiais e demais campos. As falhas
  mostram a primeira diferença sem gerar diffs gigantes; hashes continuam conferidos contra
  seus próprios CSVs (A-031, #57).

- Fixtures dos testes compartilham a preparação dos dados reais por sessão, com cópias por
  módulo; dois testes da página reutilizam o mesmo HTML, preservando as verificações (#57).

- Instruções dos agentes movidas de `CLAUDE.md` para `AGENTS.md`; o `CLAUDE.md` só importa o
  `AGENTS.md` (#22).

### Adicionado

- IPCA cheio, Brasil: extração incremental, classificação própria, fato, validações, mapa de
  harmonização, indicadores, cinco marts e relatórios de julho/2006 a setembro/2026 (#12).
  Histórico anterior e propostas de harmonização não revisadas permanecem explicitamente separados.
- Tratamento documentado do zero absoluto SIDRA, indisponibilidades por categoria e exceções
  contadas do IPCA, com testes de identidade e origens preservadas (A-033 a A-035).
- Atualização automática selecionável por índice, jobs sequenciais e dicionários/metadados
  isolados para preservar o IPCA-15.

- Projeto de preparação do IPCA cheio: ficha conferida nas APIs oficiais, entrega principal
  desde julho/2006, extensão histórica separada e dez tarefas preparadas para GitHub Projects
  (#12). A implementação e a publicação dos dados permanecem pendentes.

- Atualização automática (#9): `python -m macroaf.pipeline` (extração → harmonização → marts →
  páginas, parando na primeira falha) e o workflow `atualizacao.yml`, diário do dia 15 ao fim do
  mês, com commit na `main` só se houve mudança e os testes passaram; execução manual com opção de
  republicar.
- Marts do IPCA-15 em `data/marts/` (`python -m macroaf.marts.publicar`): categorias, mensal,
  acumulados, contribuições e difusão em CSV, dicionário de dados gerado, `data/metadata.json` e
  histórico de mudanças de série; a publicação é bloqueada se uma validação ou conferência falha
  (decisões 0006 e 0007, #8).
- Página de transformações com a seção Resultados (gráficos do acumulado em 12 meses, contribuições
  dos grupos, difusão e sazonalidade, conferência dos indicadores com o IBGE e exemplo da âncora do
  acumulado no ano, A-023), rastreio do leite até os indicadores e glossário; fatos atualizados
  depois dos indicadores (#53).
- Decisão 0006 aceita (chave dos marts) e registrada no PLANEJAMENTO 9.11; PR cita
  `Closes #N (fecha #N)` (A-027).
- Testes que exigem que todo `CLAUDE.md` contenha só `@AGENTS.md`, com `AGENTS.md` ao lado, e que
  todo `AGENTS.md` tenha o `CLAUDE.md` que o importa (A-006, #45).
- Difusão (simples e ponderada, no geral e por grupo) e sazonalidade (média e mediana por mês do
  ano em 5 anos, por série longa) (`python -m macroaf.indicators.difusao` e
  `macroaf.indicators.sazonalidade`); subitem com peso 0 fora da conta (A-026); `METODOLOGIA.md` 11
  (#44).
- Contribuições em pontos percentuais para o geral, no mês e nos acumulados, e participação no
  grupo (`python -m macroaf.indicators.contribuicoes`); a soma dos grupos reproduz o geral dentro do
  limite da reconciliação; `METODOLOGIA.md` 10 (#43).
- Acumulados por janela (3, 6, 12, 24 e 36 meses e no ano) por série longa
  (`python -m macroaf.indicators.acumulados`): oficial onde mede o mesmo que a série (A-023), calculado
  pelo índice onde falta ou onde a fonte publicou erro, com `origem` e `cesta_variavel`;
  `METODOLOGIA.md` 9 (#42).
- Índice encadeado por série longa, base 100 (`python -m macroaf.indicators.indice`), com rebase
  por divisão, acumulado em janela e no ano, e marca de cesta variável; o geral reproduz o
  número-índice da 3065 e os acumulados batem com a 3065, a 356 e a 1120 (#41).
- `METODOLOGIA.md` 8: índice encadeado e a âncora do acumulado no ano na troca de POF (A-023).
- Revisão da harmonização aplicada: 116 propostas aceitas e 14 não aceitas, com observação e
  issue de investigação (#32 a #40); 261 subitens com série contínua de mai/2000 a set/2026 (#6).
- `map_harmonizacao` do IPCA-15 (`reference/map_harmonizacao_ipca15.csv`) e série longa
  (`python -m macroaf.transform.harmonizacao`): ligações automáticas só com prova, propostas com
  evidência para revisão humana, quebras marcadas; seção de revisão na página de transformações
  (decisão 0005, #6).
- Página de revisão `docs/revisao/harmonizacao_ipca15.html` (`python -m macroaf.relatorios.revisao`):
  aceitar ou não aceitar cada proposta, com observação; decisões aplicadas ao mapa por
  `python -m macroaf.transform.harmonizacao --decisoes <json> --revisor <nome>` (#6).
- Página de transformações `docs/transformacoes/ipca15.html`, gerada dos dados
  (`python -m macroaf.relatorios.transformacoes`), com texto claro, diagramas e etapas
  interativas; teste exige que esteja em dia (decisão 0004, #5).
- `fato_ipca15` e `ref_ipca15_geral` (`python -m macroaf.transform.ipca15`) e as validações da
  seção 4.4 (`python -m macroaf.validate.ipca15`), com limites de arredondamento analíticos e
  exceções documentadas em `reference/excecoes_validacao_ipca15.csv` (#5).
- `docs/METODOLOGIA.md`: identificação das categorias (código IBGE × id SIDRA), hierarquia,
  valores e validações, com as descobertas A-012 a A-017 (#5).
- `dim_classificacao` do IPCA-15 (`python -m macroaf.transform.classificacao`): 1.951 categorias
  das quatro tabelas, hierarquia derivada do código IBGE, contrato `pandera` e testes de
  contagem e de cadeia completa até o grupo. Dependências `pandas`, `pyarrow` e `pandera` (#4).
- Extração incremental do SIDRA (`python -m macroaf.extract.atualizar`): confere o catálogo com
  os metadados, baixa só os meses ausentes, guarda revisões sem apagar e mantém a camada raw
  compactada com manifesto (decisão 0003). Carga inicial do IPCA-15 (mai/2000 a set/2026) em
  `data/raw/ibge_sidra/`. Workflow `API do IBGE` testa o acesso a partir do runner (#3).
- Catálogo de séries `config/series.yaml` com o IPCA-15 (tabelas 1646, 1387, 1705, 7062 e a
  referência 3065) e leitor com validação de esquema `macroaf.catalogo` (#2).
- Base do repositório: pacote `macroaf` em `src/`, `pyproject.toml` com `uv` (Python 3.12),
  `pytest`, `ruff` e CI no GitHub Actions (#1).
- Estrutura de agentes de IA: subagentes `revisor-metodologico`, `validador-dados` e
  `explorador-sidra`; skills `/nova-serie`, `/fechar-etapa` e `/aprender`; hook de início de sessão
  (#20).
- Registro de aprendizados (`docs/aprendizados.md`), de decisões (`docs/decisoes/`) e fichas de
  índice e de fonte (`docs/indices/ipca15.md`, `docs/fontes/ibge-sidra.md`) (#20).
- Guia `docs/AGENTES.md` (#20).
- Planejamento inicial e piloto IPCA-15.
