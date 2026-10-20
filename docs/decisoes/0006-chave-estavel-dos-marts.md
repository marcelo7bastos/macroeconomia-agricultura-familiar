# 0006. Chave estável dos marts: categoria publicada, não série

- **Situação:** aceita (PR #47, mergeado pelo mantenedor; confirmada na conversa da #53)
- **Data:** 2026-10-20
- **Issue/PR:** #8

## Contexto

O Power BI lê os marts pelas URLs do GitHub e guarda relacionamentos, filtros e indicadores
salvos pela chave das tabelas. Uma chave que muda quebra o relatório sem aviso.

A série longa tem `serie_id` (`codigo@pof_inicial`), mas ele **muda com a revisão** (METODOLOGIA
7.2): aceitar a emenda de duas séries faz a segunda sumir dentro da primeira. Isso já aconteceu: a
revisão do #6 levou de 807 para 731 séries. Vai acontecer de novo a cada investigação das issues
#32 a #40 e a cada POF nova (#27). O `serie_id` não serve de chave.

O que nunca muda é o que o IBGE publica: a categoria é identificada pelo par (tabela SIDRA, id
SIDRA) (A-012), e um valor por (categoria, mês).

## Decisão

- **Chave das linhas dos marts:** `(mes, chave_categoria)`, com `chave_categoria = "<tabela>.<id
  SIDRA>"` (ex.: `7062.7357`). É a identidade publicada pelo IBGE; não depende de nenhuma decisão
  do projeto.
- **Dimensão `dim_categoria`** com uma linha por `chave_categoria`: código IBGE, nome, nível, POF,
  pais na hierarquia **e**, como atributos, `serie_id` e `serie_nome` (nome da categoria mais
  recente da série). A série é um **agrupamento**, não uma chave: pode mudar, e o relatório que
  filtra por ela continua funcionando.
- **Indicadores da série** (índice encadeado, acumulados, contribuições) ficam em cada linha
  `(mes, chave_categoria)` a que pertencem. Cada linha tem um valor só, porque cada categoria está em
  uma série só (invariante da série longa).
- **Registro de mudanças de série:** quando uma revisão junta, separa ou cria séries,
  `reference/historico_series_<indice>.csv` registra `serie_id_antigo → serie_id_novo`, a data e a
  ligação do mapa que causou a mudança. Quem salvou um filtro por série consegue traduzir.
- Os **nomes de arquivo** em `data/marts/` continuam estáveis (regra do `AGENTS.md`); colunas só são
  acrescentadas, nunca renomeadas ou removidas sem uma decisão nova.

## Alternativas consideradas

- **`serie_id` como chave:** muda a cada revisão; quebraria o Power BI a cada investigação.
- **Chave pela categoria mais recente da série:** muda a cada POF nova, quando a série ganha um
  membro novo no fim.
- **Chave sintética sequencial (1, 2, 3...) atribuída à série:** estável só enquanto ninguém mexe
  no mapa; numa fusão, uma das chaves morre do mesmo jeito, e a chave perde o significado.
- **Código IBGE + mês:** o mesmo código tem ids diferentes entre tabelas e às vezes é outra
  categoria (A-012); numa tabela ele é único, mas entre tabelas não.

## Consequências

- Relacionamentos do Power BI ficam presos a uma identidade que o projeto não controla e que o
  IBGE não muda; revisões da harmonização mudam atributos, não chaves.
- Para ver uma série inteira, o relatório filtra pelo atributo `serie_id` (ou `serie_nome`), não por
  relacionamento. Um filtro salvo por série pode precisar de tradução após uma revisão (pelo
  histórico).
- Os marts repetem atributos da série em cada linha (mais espaço, menos junções); aceitável no
  volume do IPCA-15 (~150 mil linhas).
- Reavaliar se o IBGE passar a reaproveitar id SIDRA para outra categoria dentro da mesma tabela,
  o que nunca foi observado.
