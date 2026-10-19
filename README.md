# Macroeconomia da Agricultura Familiar

Pipeline aberto de indicadores macroeconômicos ligados à agricultura e à agricultura familiar no
Brasil, a partir de dados públicos (IBGE, Banco Central).

> **Situação:** planejamento. O piloto é o **IPCA-15**, da extração à criação de indicadores.

## Como o projeto funciona

```
APIs oficiais (IBGE/SIDRA) → extração (raw) → transformação (staging) → indicadores (marts)
                                                     ↓ validação contra séries oficiais
                                         site estático · Power BI · CSV/Parquet
```

- Os dados são atualizados automaticamente pelo GitHub Actions quando o IBGE divulga um mês novo.
- Todo indicador calculado é testado contra uma referência oficial antes de ser publicado.

## Desenvolvimento

Requer [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups      # cria o ambiente com Python 3.12 e as dependências
uv run pytest             # testes
uv run ruff check .       # lint
uv run ruff format .      # formatação
```

O CI roda lint, formatação e testes em todo push na `main` e em todo PR.

## Documentação

- [Planejamento](docs/PLANEJAMENTO.md): escopo, fontes, transformação, indicadores e decisões.
- [Decisões](docs/decisoes/) e [aprendizados](docs/aprendizados.md): o porquê das escolhas e as
  lições registradas ao longo do projeto.
- [Fichas de índices](docs/indices/) e [de fontes](docs/fontes/).
- [Agentes de IA](docs/AGENTES.md): como o Claude Code trabalha no projeto.
- [Changelog](CHANGELOG.md).
- [Backlog](../../issues?q=is%3Aissue+is%3Aopen+label%3Abacklog): ideias e próximas frentes.
- [Piloto IPCA-15](../../milestone/1): etapas em andamento.

## Licença

- Código: [MIT](LICENSE).
- Dados derivados: [CC BY 4.0](LICENSE-DADOS.md). Os dados originais são do IBGE e do Banco
  Central do Brasil e devem ser citados como fonte.
