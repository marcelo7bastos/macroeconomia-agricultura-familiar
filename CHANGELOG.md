# Changelog

Mudanças relevantes do projeto. Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## Não publicado

### Adicionado

- Base do repositório: pacote `macroaf` em `src/`, `pyproject.toml` com `uv` (Python 3.12),
  `pytest`, `ruff` e CI no GitHub Actions (#1).
- Estrutura de agentes de IA: subagentes `revisor-metodologico`, `validador-dados` e
  `explorador-sidra`; skills `/nova-serie`, `/fechar-etapa` e `/aprender`; hook de início de sessão
  (#20).
- Registro de aprendizados (`docs/aprendizados.md`), de decisões (`docs/decisoes/`) e fichas de
  índice e de fonte (`docs/indices/ipca15.md`, `docs/fontes/ibge-sidra.md`) (#20).
- Guia `docs/AGENTES.md` (#20).
- Planejamento inicial e piloto IPCA-15.
