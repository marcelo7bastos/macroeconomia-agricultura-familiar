# Banco Central do Brasil: SGS (câmbio)

- **Instituição:** Banco Central do Brasil
- **Última conferência:** 2026-11-04 (piloto do café, #62)
- **Licença:** dado público; citar o Banco Central do Brasil como fonte.

## Séries usadas

| Série SGS | Conteúdo | Frequência | Uso |
|---|---|---|---|
| 1 | Dólar americano, PTAX venda, R$/US$ | diária (dias úteis) | só validação: a média calculada dos dias úteis tem de bater com a 3698 |
| 3698 | Dólar americano, PTAX venda, média do período, R$/US$ | mensal, datada no dia 1 | converte os preços internacionais (oficial) |

A série 3697 é a mesma média, mas de **compra** (valores um pouco menores: set/2026, 5,1441 contra
5,1447 da 3698). O projeto usa venda, a convenção de conversão de preços em US$.

## Endpoints

`https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados?formato=json&dataInicial=DD/MM/AAAA&dataFinal=DD/MM/AAAA`

Resposta: lista JSON de `{"data": "DD/MM/AAAA", "valor": "5.1570"}`, valor em texto com ponto
decimal e quatro casas.

## Limites e paginação

- Séries diárias: no máximo **10 anos por consulta**. Acima disso a API devolve **HTTP 406** com
  uma mensagem em JSON explicando o limite (conferido em 2026-11-04, 2006–2026).
- O extrator pede **um mês por consulta** e guarda um arquivo por mês (`data/raw/bcb_sgs/<serie>/AAAAMM.json.gz`).
  Só meses completos: o mês corrente fica de fora até terminar, porque a média oficial (3698) só
  é publicada depois.

## Formato e valores especiais

- Dias sem PTAX (fins de semana e feriados) simplesmente não aparecem.
- **Média mensal oficial = média aritmética simples dos dias úteis**, arredondada a 4 casas.
  Conferido em 250 meses (jan/2006–out/2026): a maior diferença entre a média calculada e a
  3698 é 0,00005, isto é, só arredondamento (dois meses no meio do intervalo: abr/2009 e nov/2022).
  O pipeline valida com esse limite.

## Falhas conhecidas e como tratar

- 406 por intervalo longo: não acontece com a consulta mensal.
- Intervalo sem valor: **HTTP 404** com `{"erro": {"statusCode": 404, "detail": "...Value(s) not
  found"}}` (conferido em 2026-11-04 na 3698 de nov/2026). Na 3698 do mês recém-fechado, isso é
  pendência: nada é gravado e a coleta seguinte tenta de novo. Em qualquer outro mês, o extrator
  falha (não grava arquivo vazio).

## Acesso a partir dos ambientes

- Sessão na nuvem: exige `api.bcb.gov.br` na lista de domínios permitidos.
- GitHub Actions: sem restrição conhecida.
