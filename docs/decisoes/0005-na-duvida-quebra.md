# 0005. Na dúvida, quebra

- **Situação:** aceita
- **Data:** 2026-10-19
- **Issue/PR:** #6

## Contexto

A série longa do IPCA-15 junta quatro tabelas, uma por POF. A cada troca, o IBGE mantém, renomeia,
funde, divide, cria e encerra categorias. O código IBGE igual não garante a mesma categoria: o
IBGE cria um id SIDRA novo quando reformula a categoria e mantém o código (A-012), e a mudança vai
de grafia a produto diferente. São cerca de 1.600 ligações; revisar todas à mão é inviável, e
emendar por regra frouxa mistura produtos diferentes sem ninguém ver.

## Decisão

- Emendar duas categorias numa série contínua exige **prova**: o mesmo id SIDRA. Id novo, mesmo
  com o nome igual depois de normalizar, é proposta (o id identifica a definição, A-012).
- Qualquer outra ligação é **proposta**, com a evidência (nomes, ids, critério, pesos nas pontas),
  e só emenda depois de **revisada por uma pessoa** (`situacao = revisado`, com o revisor).
- Proposta não revisada ou rejeitada conta como **quebra marcada**: a série termina e outra
  começa, e a saída e a entrada dizem por quê.
- A revisão é feita numa página interativa que grava as decisões (aceita; não aceita com
  observação); as decisões são aplicadas ao mapa por comando, com o nome do revisor.
- O mapa fica versionado em `reference/`, e a revisão é preservada quando ele é regerado.

## Alternativas consideradas

- **Emendar por código IBGE:** juntaria Leite pasteurizado e Leite longa vida, Refrigerante e
  Refrigerante e água mineral.
- **Emendar por similaridade de nome:** a primeira tentativa pareou "Melão" com "Telha" e espécies
  de peixe diferentes entre si (A-019).
- **Revisar tudo à mão antes de publicar:** inviável no volume e desnecessário onde o id prova a
  identidade.

## Consequências

- Sem revisão humana, 212 subitens já têm série contínua de mai/2000 a set/2026; o resto fica
  quebrado até a revisão, sempre de forma visível.
- O erro possível é uma série curta demais (falta emendar), nunca uma série emendada errado.
- A revisão é trabalho do mantenedor, na página `docs/revisao/harmonizacao_ipca15.html`.
