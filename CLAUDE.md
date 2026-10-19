# Instruções para o Claude Code

- Leia `docs/PLANEJAMENTO.md` antes de começar qualquer tarefa; ele é a fonte das decisões do projeto.
- Idioma: português em código (nomes de variáveis, funções, colunas), comentários, docs, commits e issues.
- Piloto atual: **IPCA-15**. Outras frentes ficam como issues com o rótulo `backlog`; não implemente
  sem uma issue correspondente.
- Hierarquia da classificação 315 do SIDRA: derive pelo código IBGE no nome da categoria
  (1 dígito = grupo, 2 = subgrupo, 4 = item, 7 = subitem), nunca pelo campo `nivel` dos metadados.
- Prefira o dado oficial; só calcule o que o IBGE/BCB não publica. Todo indicador calculado precisa
  de teste contra referência oficial ou identidade contábil.
- Nunca emende séries de POFs diferentes em silêncio: use `map_harmonizacao` e marque quebras.
- Nomes de arquivos em `data/marts/` são estáveis (o Power BI lê pelas URLs do raw do GitHub).
- Fontes de dados só por API oficial ou CSV versionado em `reference/`; nada de links de planilhas.
- APIs usadas: `apisidra.ibge.gov.br` e `servicodados.ibge.gov.br`.
