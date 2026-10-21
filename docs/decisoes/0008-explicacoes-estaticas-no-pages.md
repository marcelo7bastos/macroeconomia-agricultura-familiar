# 0008. Explicações estáticas no GitHub Pages

- **Situação:** proposta em revisão no PR da issue #59; primeira publicação explicitamente autorizada pelo mantenedor na conversa de 21/10/2026.
- **Data:** 2026-10-21.
- **Issue:** #59; relacionada às #18 e #26.

## Contexto

O mantenedor pediu explicações técnicas e de gestão para IPCA e IPCA-15, com HTML interativo,
aplicação da skill `explicar-conteudo` e acesso posterior pelo GitHub Pages. Já existem HTMLs
que explicam as transformações (decisão 0004); não é necessário esperar a implementação de um
site Quarto para disponibilizá-los.

## Proposta implementada nesta entrega

Gerar HTML estático a partir dos marts e metadados conferidos, com dados incorporados, sem
backend, autenticação ou consulta à API do IBGE na navegação. Preservar os relatórios técnicos
e adicionar uma leitura de gestão com exploração dos números e aprofundamento em engenharia.

Publicar uma árvore estática na branch `gh-pages`, fonte `/` do Pages, separada da `main`.
A primeira publicação autorizada não realiza merge de código. Após o merge do PR, o workflow
`pages.yml` mantém a publicação, inclusive após a atualização de dados por `workflow_run`.
A cópia do site preserva a posição de `docs/`, `data/marts/` e `reference/`, para manter links
relativos e CSVs da mesma publicação. O raw e caches não fazem parte do artefato.

## Alternativas consideradas

- **Aguardar Quarto:** acrescentaria uma etapa que o pedido de explicação atual não exige; a
  escolha de Quarto como site futuro permanece aberta na issue #18.
- **Hospedar aplicação com backend:** cria operação, autenticação e dependências sem necessidade
  demonstrada para ler e explorar esta publicação.
- **GitHub Pages apenas com deploy-pages/OIDC:** é uma alternativa válida. A branch dedicada
  permite a publicação inicial autorizada antes do merge e o histórico dos artefatos; o workflow
  solicita explicitamente o build, pois push com `GITHUB_TOKEN` não o dispara sozinho.
- **Substituir o relatório técnico pelo gerencial:** perderia rastreio e detalhes já produzidos;
  por isso os dois materiais coexistem e se ligam por navegação.

## Consequências

A leitura gerencial funciona sem CDN e mantém o snapshot incorporado; a atualização exige nova
geração e publicação. O site não é uma API em tempo real. Os CSVs completos também ficam no
artefato para preservar coerência de versão, aumentando o tamanho da branch de publicação.

A manutenção envolve dois workflows: preparar dados e publicar site. Falha de implantação não
altera os dados na `main`, nem comprova indisponibilidade do IBGE. Uma publicação com sucesso
não equivale à revisão editorial do usuário. Reavaliar a hospedagem se houver necessidade real
de backend, maior catálogo de índices ou adoção de Quarto.
