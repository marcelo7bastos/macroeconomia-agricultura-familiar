# IBGE: SIDRA e API de agregados

- **Instituição:** Instituto Brasileiro de Geografia e Estatística
- **Última conferência:** 2026-10-19

## Endpoints

| Uso | URL |
|---|---|
| Metadados de uma tabela (variáveis, classificações, período) | `https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados` |
| Períodos disponíveis | `https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/periodos` |
| Valores | `https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all/v/{variaveis}/p/{periodos}/c315/{categorias}` |

## Limites e paginação

A API SIDRA limita o número de valores por requisição. As consultas são divididas por variável e por
faixa de períodos (`PLANEJAMENTO.md`, 3.2). O limite exato e o comportamento ao ultrapassá-lo devem
ser medidos na #3 e registrados aqui.

## Formato e valores especiais

- A classificação aparece com o código IBGE no nome da categoria (ex.: `1101002.Arroz`); é desse
  código que sai a hierarquia, não do campo `nivel` (A-001).
- Valores especiais do SIDRA (`...`, `-`, `X` e similares) precisam de tratamento explícito na
  transformação; levantar na #3.

## Falhas conhecidas e como tratar

- Retentativas com espera exponencial e timeout explícito (`PLANEJAMENTO.md`, 3.2).
- Detecção de mês novo pelos metadados (`periodicidade.fim`) antes de baixar valores.

## Acesso a partir dos ambientes

- **Sessão do Claude Code na nuvem:** em 2026-10-19 a política de rede do ambiente bloqueava os dois
  domínios (403 no proxy). É preciso incluir `servicodados.ibge.gov.br` e `apisidra.ibge.gov.br` em
  *Allowed domains* nas configurações do ambiente (A-004).
- **GitHub Actions:** a testar na #3.
