# Fichas de fontes

Uma ficha por fonte de dados (instituição ou API). A ficha registra como acessar, limites,
comportamentos estranhos e o que fazer quando a fonte falha. Detalhes de cada índice ficam em
`docs/indices/`.

| Fonte | Ficha |
|---|---|
| IBGE (SIDRA e API de agregados) | [ibge-sidra.md](ibge-sidra.md) |

## Modelo

```markdown
# <Fonte>

- **Instituição:**
- **Última conferência:** AAAA-MM-DD

## Endpoints
## Limites e paginação
## Formato e valores especiais
## Falhas conhecidas e como tratar
## Acesso a partir dos ambientes (sessão na nuvem, GitHub Actions)
```
