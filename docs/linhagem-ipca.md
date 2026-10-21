# Dicionário de linhagem auditável — IPCA geral

Escopo: cinco CSVs da publicação, Brasil, dados até 2026-09. Fonte: IBGE/SIDRA 2938, 1419, 7060; referência geral 1737. A interface navegável é [docs/gestao/ipca-linhagem.html](../gestao/ipca-linhagem.html).

## Método da auditoria

- Campos oficiais: variáveis SIDRA 63 (variação mensal), 66 (peso), 69 (acumulado no ano) e 2265 (12 meses). Preservados como publicados; `-` = 0 e `...` = ausência, conforme regras de tratamento.
- Índice encadeado: `indicators/indice.py::montar_indice`, `100*exp(cumsum(log(1+variacao_mensal/100)))` por `serie_id`; quebra de série reinicia base.
- Acumulados: `indicators/acumulados.py::montar_acumulados`, privilegia valor oficial válido, senão composição pelo índice; exceções publicadas e início da série impedem substituição indiscriminada.
- Contribuições: `indicators/contribuicoes.py::contribuicao_mensal` e `contribuicao_acumulada`, pondera mês por peso e normaliza pela soma dos nove grupos; janelas reescaladas pelo índice geral.
- Sazonalidade: `indicators/sazonalidade.py::montar_sazonalidade`, média e mediana móvel de cinco anos completos consecutivos na mesma série.
- Difusão: `indicators/difusao.py::montar_difusao`, subitens de peso positivo e variação positiva; pesos zero são excluídos.
- Marcadores e identidades: `marts/publicar.py`, `transform/classificacao.py`, `transform/harmonizacao.py`. Chave publicada `tabela_sidra.codigo_sidra`; `serie_id` é sujeito a revisão de harmonização.

## Ressalvas

A navegação contém todos os campos descritos no contrato de CSV e indica quando a linhagem é uma regra de identificação e não uma fórmula matemática. Para determinados campos de identificação, a função apontada é o módulo de responsabilidade e a descrição é uma regra sem auditoria linha a linha de implementação. 63 propostas de harmonização pendentes permanecem quebras. A tabela 1737 não contém detalhamento por categoria desde 1979.

## Validação sugerida

Regenerar página com `uv run python -m macroaf.relatorios.gestao`; verificar que a sétima aba da página IPCA apresenta link para o dicionário. Executar `uv run pytest` e validar navegação por teclado e mobile no navegador. Não editar os CSVs ou realizar deploy antes dos testes.
