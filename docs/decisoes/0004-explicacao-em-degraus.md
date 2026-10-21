# 0004. Explicação em degraus, gerada a partir dos dados

- **Situação:** aceita
- **Data:** 2026-10-19
- **Issue/PR:** #5

## Contexto

O mantenedor precisa avaliar e aprender o que foi feito com os dados: que transformações foram
aplicadas, como as tabelas se juntam, o que já existe e o que falta. Documentos escritos à mão
envelhecem quando o código muda, e uma explicação que muda de formato pode mudar os fatos sem
ninguém perceber.

## Decisão

1. Cada índice tem uma página de transformações em `docs/transformacoes/<indice>.html`, organizada
   em degraus de explicação:
   1. **texto claro** em português (o que foi feito, quem faz o quê, decisões tomadas, dúvidas em
      aberto), inspirado nos princípios de linguagem técnica simplificada, sem se dizer conforme a
      norma ASD-STE100, que é específica do inglês;
   2. **diagramas** do fluxo dos dados e da linha do tempo das tabelas;
   3. **página interativa**: etapas clicáveis (entrada, regra, saída, comando, código), rastreio de
      um valor da API até o fato, filtro das exceções e visão executiva ou técnica;
   4. **vídeo** fica para quando houver necessidade de apresentar a terceiros (não feito).
2. A página é **gerada pelo código** (`python -m macroaf.relatorios.transformacoes --indice <indice>`)
   a partir do catálogo, do raw, do staging, das validações, das exceções e limites em
   `reference/`, de `aprendizados.md` e do `PLANEJAMENTO.md`. Nenhum número é escrito à mão.
3. **Mudar o formato não muda os fatos.** Uma dúvida em aberto continua dúvida na página; o que não
   existe aparece como "a fazer". A lista de dúvidas fica no gerador com a fonte de cada uma.
4. Um teste regera a página e falha se o arquivo do repositório estiver diferente: toda etapa que
   muda uma transformação regera a página no mesmo PR.

## Alternativas consideradas

- **Documento escrito à mão:** envelhece em silêncio e pode divergir dos dados.
- **Página só publicada fora do repositório:** não acompanha o código nem passa por revisão no PR.
- **Notebook:** mistura execução e explicação, exige ambiente para ler e não tem teste de atualização.

## Consequências

- O mantenedor lê a mesma verdade que os testes conferem.
- Um índice novo ganha a página com `--indice`, desde que siga a estrutura do IPCA-15 (catálogo,
  dim, fato, referência, validações). Índices de estrutura diferente (PIB, Pronaf) precisarão de
  uma coleta própria; o modelo da página é compartilhado.
- O texto fixo do gerador descreve o código e precisa mudar junto com ele; o revisor metodológico
  confere isso.
