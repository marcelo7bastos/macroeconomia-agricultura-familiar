# Macroeconomia da Agricultura Familiar

Pipeline aberto de indicadores macroeconômicos ligados à agricultura e à agricultura familiar no
Brasil. A fonte implementada é o IBGE/SIDRA; séries do Banco Central permanecem no backlog.

> **Situação em 20/10/2026:** IPCA-15 (mai/2000–set/2026) e IPCA cheio
> (jul/2006–set/2026) publicados, Brasil, até subitem. O [PR #58](https://github.com/marcelo7bastos/macroeconomia-agricultura-familiar/pull/58)
> foi integrado à `main`. A cobertura corrente está em [data/metadata.json](data/metadata.json).
> O IPCA mantém 63 propostas de harmonização como quebras; histórico anterior a julho/2006,
> painel e indicador específico da agricultura familiar são entregas separadas.

## Como o projeto funciona

```
APIs oficiais (IBGE/SIDRA) → extração (raw) → transformação (staging) → indicadores (marts)
                                                     ↓ validação contra séries oficiais
                                         site estático · Power BI · CSV
```

- Os dados são atualizados automaticamente pelo GitHub Actions quando o IBGE divulga um mês novo
  ([`atualizacao.yml`](.github/workflows/atualizacao.yml)): só há commit se tudo passa.
- Todo indicador calculado é testado contra uma referência oficial antes de ser publicado.

## Desenvolvimento

Requer [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups --locked # cria o ambiente com Python 3.12 e as dependências
uv run pytest             # testes
uv run ruff check .       # lint
uv run ruff format .      # formatação
```

O CI roda lint, formatação e testes em todo push na `main` e em todo PR.

Para atualizar um índice do IBGE até os CSVs:

```bash
uv run python -m macroaf.pipeline --indice ipca              # IPCA, se houver novidade
uv run python -m macroaf.pipeline --indice ipca15            # IPCA-15
uv run python -m macroaf.pipeline --indice ipca15 --forcar   # republica mesmo sem novidade
```

Ou etapa por etapa, para IPCA-15 (para IPCA, acrescente `--indice ipca` a cada comando; decisão [0003](docs/decisoes/0003-extracao-incremental.md)):

```bash
uv run python -m macroaf.extract.atualizar --verificar   # só confere o que falta
uv run python -m macroaf.extract.atualizar               # baixa
uv run python -m macroaf.transform.ipca15                # staging (dim, fato e referência)
uv run python -m macroaf.validate.ipca15                 # validações (falha = não publicar)
uv run python -m macroaf.transform.harmonizacao          # mapa entre POFs e série longa
uv run python -m macroaf.marts.publicar                  # confere e publica data/marts/*.csv
uv run python -m macroaf.relatorios.transformacoes       # página docs/transformacoes/ipca15.html
```

## Explicações para gestores

[IPCA geral](https://marcelo7bastos.github.io/macroeconomia-agricultura-familiar/docs/gestao/ipca.html) ·
[IPCA-15](https://marcelo7bastos.github.io/macroeconomia-agricultura-familiar/docs/gestao/ipca15.html).
Seis abas por índice: gestão, exploração dos dados, contratos, programação, qualidade e fontes.
Os relatórios técnicos anteriores continuam disponíveis. Veja [como publicar](docs/PUBLICACAO.md).

## Documentação

- [Índice da documentação](docs/README.md): navegação por assunto e regras de manutenção.
- [Guia dos dados](data/README.md): camadas, índices, CSVs e chaves de consumo.
- [Operação](docs/OPERACAO.md): comandos dos dois índices, Actions e recuperação após falha.
- [Estrutura e proposta de organização](docs/ESTRUTURA.md): pastas atuais e migrações sugeridas.

- [Planejamento](docs/PLANEJAMENTO.md): escopo, fontes, transformação, indicadores e decisões.
- Dicionários dos marts: [IPCA-15](data/marts/README.md) e [IPCA](data/marts/ipca_README.md).
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
- [Piloto IPCA-15](../../milestone/1): etapas e histórico do marco.

O workflow consulta os dois índices diariamente às **09:23 de Brasília** e permite selecionar
`ipca`, `ipca15` ou `todos` na execução manual. O CLI usa um índice por comando. A publicação
automática só grava mudanças após o pipeline e os testes passarem; confira a execução em Actions.

## Licença

- Código: [MIT](LICENSE).
- Dados derivados: [CC BY 4.0](LICENSE-DADOS.md). Os dados originais são do IBGE e do Banco
  Central do Brasil e devem ser citados como fonte.
