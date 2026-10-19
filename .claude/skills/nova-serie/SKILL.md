---
name: nova-serie
description: Roteiro para incluir um índice, tabela ou série nova no projeto (ex. IPCA cheio, PIB, Selic) - conhecer a fonte, criar a ficha, registrar no catálogo config/series.yaml e abrir a issue. Use quando o usuário quiser adicionar um índice ou fonte, ou pedir /nova-serie.
---

# /nova-serie

Um índice novo entra no projeto por **configuração e documentação**, não por código ou agente novo.
O código só muda quando a fonte tiver estrutura que o pipeline ainda não trata.

## 1. Issue

Confirme que existe issue para a série (rótulo `backlog` ou `fonte-de-dados`). Se não existir,
crie e pare para o mantenedor priorizar; não implemente frente fora do piloto sem issue.

## 2. Conhecer a fonte

Acione o subagente `explorador-sidra` (fontes IBGE) com as tabelas candidatas. Para fontes não IBGE
(BCB/SGS, SICOR, Conab), faça o mesmo levantamento manualmente na API oficial. Resultado: ficha em
`docs/indices/<indice>.md` e, se a fonte for nova, `docs/fontes/<fonte>.md`.

## 3. Comparar com o que existe

- A estrutura é igual à de um índice já tratado (ex.: IPCA cheio × IPCA-15)? Então basta
  configuração.
- O que difere (classificação, variáveis, POFs, periodicidade)? Liste na ficha e na issue.
- Qual é a referência oficial para validar o que for calculado?

## 4. Catálogo

Adicione as entradas em `config/series.yaml` (fonte, tabela, variáveis, período, unidade, versão da
POF), seguindo as entradas existentes. Se o catálogo ainda não existir, descreva as entradas na issue.

## 5. Registrar

- Atualize a tabela de escopo do `docs/PLANEJAMENTO.md` se a situação da frente mudou.
- Rode `/aprender` para peculiaridades da fonte que valham para além da ficha.
- Feche com `/fechar-etapa`.
