# Changelog

Mudanças relevantes do projeto. Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## Não publicado

### Alterado

- Instruções dos agentes movidas de `CLAUDE.md` para `AGENTS.md`; o `CLAUDE.md` só importa o
  `AGENTS.md` (#22).

### Adicionado

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
