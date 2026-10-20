# Decisões

Registro de decisões de arquitetura e método (ADRs). Cada decisão que teve alternativas e
consequências ganha um arquivo `NNNN-titulo-curto.md`. A seção 9 do `PLANEJAMENTO.md` é o índice
resumido; o contexto completo fica aqui.

Uma decisão não é apagada nem reescrita: quando muda, cria-se outra que a substitui, e a antiga
recebe `Situação: substituída por NNNN`.

| # | Decisão | Situação |
|---|---|---|
| [0001](0001-memoria-dos-agentes-no-repositorio.md) | Memória dos agentes no próprio repositório | aceita |
| [0002](0002-agentes-por-funcao.md) | Agentes por função, não por índice | aceita |
| [0003](0003-extracao-incremental.md) | Extração incremental, compilação completa | aceita |
| [0004](0004-explicacao-em-degraus.md) | Explicação em degraus, gerada a partir dos dados | aceita |
| [0005](0005-na-duvida-quebra.md) | Na dúvida, quebra (emenda de séries entre POFs) | aceita |
| [0006](0006-chave-estavel-dos-marts.md) | Chave estável dos marts: categoria publicada, não série | aceita |

## Modelo

```markdown
# NNNN. Título

- **Situação:** proposta | aceita | substituída por NNNN
- **Data:** AAAA-MM-DD
- **Issue/PR:** #N

## Contexto
O problema e as restrições.

## Decisão
O que foi decidido.

## Alternativas consideradas
- Alternativa: por que não.

## Consequências
O que fica mais fácil, o que fica mais difícil, quando reavaliar.
```
