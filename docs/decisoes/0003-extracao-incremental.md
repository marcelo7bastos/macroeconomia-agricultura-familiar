# 0003. Extração incremental, compilação completa

- **Situação:** aceita
- **Data:** 2026-10-19
- **Issue/PR:** #3

## Contexto

O IPCA-15 sai uma vez por mês, com data de divulgação que varia. O projeto guarda o raw no
repositório (decisão 9.1) e publica marts com nomes estáveis que o Power BI lê pelo GitHub. Um mês
da tabela 7062 tem 1.788 registros: 560 KB em JSON e 35 KB compactado. A série completa do
IPCA-15 tem cerca de 320 tabela × mês de dados mais 317 meses da referência 3065.

## Decisão

1. **Extração incremental.** A cada execução, os metadados de cada tabela são conferidos com o
   catálogo e só os meses ausentes no raw são baixados, um arquivo por tabela × mês. Tabelas
   fechadas (1646, 1387, 1705) são baixadas uma vez; só as abertas (7062, 3065) recebem meses novos.
2. **Raw compactado e imutável.** `data/raw/<fonte>/<tabela>/<AAAAMM>.json.gz`, com o corpo exato
   da resposta da API (gzip com `mtime=0`, determinístico) e uma linha por arquivo em
   `manifesto.csv` (URL, data da coleta, SHA-256 do original, número de registros).
3. **Revisões guardadas ao lado.** Nas tabelas abertas, os 3 últimos meses são baixados de novo a
   cada execução. Se o conteúdo mudou, grava-se `<AAAAMM>.r2.json.gz` (r3, ...) sem apagar o
   anterior; a compilação usa a revisão mais recente.
4. **Compilação completa.** Staging e marts são recalculados a partir de todo o raw em toda
   execução. O staging não é versionado (é derivado); os marts são.
5. **Verificação diária na janela de divulgação** (≈ dias 18 a 31), custando só a consulta aos
   metadados quando não há mês novo. A API de calendário do IBGE fica como alternativa a avaliar.
6. **Catálogo divergente interrompe a extração** antes de baixar valores (código de saída 2).

## Alternativas consideradas

- **Raw sem compactação:** cerca de 180 MB no repositório só para o IPCA-15, contra cerca de 11 MB.
- **Uma requisição por faixa de meses e arquivo por faixa:** menos requisições na carga inicial, mas
  o arquivo deixa de corresponder a um mês e a extração incremental fica mais complexa.
- **Staging e marts incrementais (anexar o mês novo):** mais rápido, mas acumula erros e torna o
  resultado dependente do histórico de execuções; a compilação completa leva segundos.
- **Sobrescrever o mês revisado:** perde a evidência de que a fonte mudou o dado.

## Consequências

- O mesmo raw sempre gera os mesmos marts (reprodutível).
- Revisões do IBGE ficam visíveis no manifesto e, depois da #8, no `metadata.json`.
- A carga inicial faz cerca de 630 requisições (uma por tabela × mês); as seguintes, poucas.
- Troca de POF (nova tabela) é tratada pelo catálogo; roteiro em #27.
