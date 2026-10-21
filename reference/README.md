# Referências versionadas

Arquivos que registram correspondências, evidências e decisões usadas na transformação.
Não são cache nem saídas descartáveis. Cada índice tem arquivos próprios; não transferir decisões
ou exceções do IPCA-15 para o IPCA por analogia.

| Padrão atual | Finalidade | Como atualizar |
|---|---|---|
| `map_harmonizacao_<indice>.csv` | Ligações entre categorias de POFs e decisões de revisão | Gerador propõe; revisão humana decide os casos incertos |
| `excecoes_validacao_<indice>.csv` | Escopo, justificativa, contagem e meses com erro publicado | Somente após diagnóstico e evidência da fonte |
| `limites_validacao_<indice>.csv` | Limites específicos documentados, quando existentes | Não ampliar para fazer um teste passar |
| `historico_series_<indice>.csv` | Mudanças de série entre publicações | Gerado pelo publicador; preservar o histórico anterior |
| `diagnostico_acumulado_ano_ipca.csv` | Evidência independente dos 239 valores anuais do IPCA | Conferido por identidade contábil e teste, A-035 |

A ausência de linhas em um arquivo de limites não dispensa as validações: valem os limites
analíticos do pipeline. Exceções são contadas exatamente; uma mudança na contagem exige investigação.

A revisão de harmonização usa as páginas de [`docs/revisao/`](../docs/revisao/) e o comando
`macroaf.transform.harmonizacao --decisoes <json> --revisor <nome> --indice <indice>`.
Proposta não revisada permanece quebra. Os comandos completos estão em
[Operação](../docs/OPERACAO.md); as regras, na [Metodologia](../docs/METODOLOGIA.md).

Uma futura separação em `reference/<indice>/` está proposta em
[Estrutura](../docs/ESTRUTURA.md), com migração conjunta de código, testes e documentos.
Os caminhos atuais continuam válidos.
