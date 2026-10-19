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

Para atualizar a camada raw com os meses que faltam (decisão
[0003](docs/decisoes/0003-extracao-incremental.md)):

```bash
uv run python -m macroaf.extract.atualizar --verificar   # só confere o que falta
uv run python -m macroaf.extract.atualizar               # baixa
uv run python -m macroaf.transform.ipca15                # staging (dim, fato e referência)
uv run python -m macroaf.validate.ipca15                 # validações (falha = não publicar)
uv run python -m macroaf.transform.harmonizacao          # mapa entre POFs e série longa
uv run python -m macroaf.relatorios.transformacoes       # página docs/transformacoes/ipca15.html
```

## Documentação

- [Planejamento](docs/PLANEJAMENTO.md): escopo, fontes, transformação, indicadores e decisões.
- [Transformações do IPCA-15](docs/transformacoes/ipca15.html): página interativa, gerada dos
  dados, com o caminho da API ao fato, como as tabelas se juntam e o que existe.
- [Metodologia](docs/METODOLOGIA.md): como as categorias são identificadas, os valores tratados
  e os dados validados, com as descobertas que justificam cada regra.
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
