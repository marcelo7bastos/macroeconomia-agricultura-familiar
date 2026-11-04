# Fichas de fontes

Uma ficha por fonte de dados (instituição ou API). A ficha registra como acessar, limites,
comportamentos estranhos e o que fazer quando a fonte falha. Detalhes de cada índice ficam em
`docs/indices/`.

| Fonte | Ficha |
|---|---|
| IBGE (SIDRA e API de agregados) | [ibge-sidra.md](ibge-sidra.md) |
| Banco Central do Brasil (SGS, câmbio) | [bcb-sgs.md](bcb-sgs.md) |
| FMI (Primary Commodity Price System) | [fmi-pcps.md](fmi-pcps.md) |
| Banco Mundial (Pink Sheet) | [banco-mundial-cmo.md](banco-mundial-cmo.md) |

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
