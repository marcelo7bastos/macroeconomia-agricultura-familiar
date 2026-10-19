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

## Documentação

- [Planejamento](docs/PLANEJAMENTO.md): escopo, fontes, transformação, indicadores e decisões.
- [Backlog](../../issues?q=is%3Aissue+is%3Aopen+label%3Abacklog): ideias e próximas frentes.
- [Piloto IPCA-15](../../milestone/1): etapas em andamento.

## Licença

- Código: [MIT](LICENSE).
- Dados derivados: [CC BY 4.0](LICENSE-DADOS.md). Os dados originais são do IBGE e do Banco
  Central do Brasil e devem ser citados como fonte.
