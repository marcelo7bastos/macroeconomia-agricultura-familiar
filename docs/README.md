# Documentação do projeto

Revisão geral em **21/10/2026**, após o merge do [PR #58](https://github.com/marcelo7bastos/macroeconomia-agricultura-familiar/pull/58).
IPCA-15 e IPCA têm dados publicados; os próximos índices e os painéis permanecem no backlog.
A cobertura corrente e a coleta de cada índice estão em [`data/metadata.json`](../data/metadata.json).

| Necessidade | Documento |
|---|---|
| Começar a usar ou desenvolver | [README do projeto](../README.md) |
| Escolher CSVs e entender as camadas | [Guia dos dados](../data/README.md) |
| Consultar colunas do IPCA-15 / IPCA | [IPCA-15](../data/marts/README.md) / [IPCA](../data/marts/ipca_README.md) |
| Explorar a implementação como gestor | [IPCA](gestao/ipca.html) / [IPCA-15](gestao/ipca15.html) |
| Publicar e conferir o GitHub Pages | [Publicação](PUBLICACAO.md) |
| Atualizar, testar, recuperar uma execução | [Operação](OPERACAO.md) |
| Entender as pastas e avaliar melhorias | [Estrutura e proposta de organização](ESTRUTURA.md) |
| Conhecer o escopo e as próximas entregas | [Planejamento](PLANEJAMENTO.md) |
| Conferir regras, fórmulas e tolerâncias | [Metodologia](METODOLOGIA.md) |
| Consultar tabelas e peculiaridades de um índice | [Fichas de índices](indices/README.md) |
| Consultar a API e os sinais especiais | [Fichas de fontes](fontes/README.md) |
| Entender mapas, limites e exceções | [Referências](../reference/README.md) |
| Examinar transformações e resultados | [IPCA-15](transformacoes/ipca15.html) / [IPCA](transformacoes/ipca.html) |
| Revisar ligações entre POFs | [IPCA-15](revisao/harmonizacao_ipca15.html) / [IPCA](revisao/harmonizacao_ipca.html) |
| Consultar decisões e descobertas | [Decisões](decisoes/README.md) / [Aprendizados](aprendizados.md) |
| Trabalhar com agentes | [Fluxo dos agentes](AGENTES.md) / [Instruções](../AGENTS.md) |
| Acompanhar a preparação do IPCA | [Projeto IPCA](projetos/ipca-geral.md) |
| Saber o que foi revisado | [Revisão documental](REVISAO_DOCUMENTAL.md) / [Changelog](../CHANGELOG.md) |

## Como manter a documentação

A ficha descreve **a fonte e a cobertura**; a metodologia descreve **o tratamento dos dados**;
o guia de operação reúne **comandos e recuperação**; o planejamento acompanha **escopo e pendências**.
As decisões e os aprendizados preservam contexto histórico: não se deve reescrevê-los como se as
conclusões atuais já fossem conhecidas na data original.

Dicionários e páginas HTML são gerados. Corrija o gerador e regenere o documento quando seu
conteúdo precisar mudar. Os caminhos atuais e os geradores estão em [ESTRUTURA.md](ESTRUTURA.md).
Uma proposta de organização não altera o contrato público até sua migração ser implementada e revisada.
