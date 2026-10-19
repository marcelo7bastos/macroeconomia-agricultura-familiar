# Agentes de IA no projeto

Como o Claude Code trabalha neste repositório: quem faz o quê, quais procedimentos existem e como o
que é aprendido fica registrado. As razões estão nas decisões [0001](decisoes/0001-memoria-dos-agentes-no-repositorio.md)
e [0002](decisoes/0002-agentes-por-funcao.md).

## Visão geral

```
issue ──▶ sessão principal (orquestra) ──▶ branch + código + testes
                 │
                 ├─ explorador-sidra ......... conhece a fonte, escreve a ficha
                 ├─ validador-dados .......... roda validações, diagnostica falhas
                 └─ revisor-metodologico ..... parecer antes do PR
                 │
                 └─ /fechar-etapa ──▶ /aprender ──▶ PR ──▶ revisão do mantenedor
```

## Subagentes (`.claude/agents/`)

| Agente | Função | Pode editar? | Quando acionar |
|---|---|---|---|
| `revisor-metodologico` | Confere a mudança contra as regras do projeto e devolve um parecer (aprovado, ressalvas, bloqueado) | não | antes de todo PR |
| `validador-dados` | Roda as validações da seção 4.4 do planejamento e isola a causa de cada falha | não | quando uma validação falhar; antes de publicar marts |
| `explorador-sidra` | Levanta metadados de tabelas do IBGE e escreve as fichas | só `docs/indices/` e `docs/fontes/` | índice ou fonte nova; conferência de metadados |

Não há um agente por índice: o que muda entre índices é configuração (`config/series.yaml`) e ficha
(`docs/indices/`). A sessão principal faz o papel de orquestrador.

## Skills (`.claude/skills/`)

| Skill | O que faz |
|---|---|
| `/nova-serie` | Roteiro para incluir índice ou fonte: issue → explorador → ficha → catálogo |
| `/fechar-etapa` | Checklist antes do PR: código, revisão metodológica, documentação, aprendizados |
| `/aprender` | Registra uma lição em `docs/aprendizados.md` e a promove (teste, validação, regra, ficha) |

## Rotinas

| Rotina | Onde | Situação |
|---|---|---|
| Hook de início de sessão: instala dependências na nuvem e mostra as lições recentes | `.claude/hooks/session-start.sh` | ativo |
| CI (ruff e pytest; validações de dados a partir da #5) em todo push e PR | `.github/workflows/ci.yml` | ativo |
| Verificação de acesso às APIs do IBGE e do catálogo (PRs de extração e semanal) | `.github/workflows/api-ibge.yml` | ativo |
| Página de transformações por índice, regerada em todo PR que muda transformação (teste exige) | `docs/transformacoes/` | ativo |
| Atualização automática quando o IBGE divulga mês novo | GitHub Actions | #9 |
| Retrospectiva semanal: lê PRs, issues e falhas e propõe ajustes nas regras | tarefa agendada | depois do piloto |

## Aprendizado contínuo

O ciclo é **descoberta → registro → promoção → revisão**:

1. Ao descobrir algo não óbvio, o agente roda `/aprender`.
2. A lição entra em [`aprendizados.md`](aprendizados.md) e é promovida para a forma mais forte que
   couber: teste > validação no pipeline > regra no `AGENTS.md` > ficha.
3. `/fechar-etapa` pergunta, ao fim de toda issue, o que a próxima sessão precisaria saber.
4. O mantenedor revisa no PR toda mudança em regras e decisões.
5. O hook de início de sessão lembra as lições mais recentes.

## Onde fica cada coisa

| Conhecimento | Arquivo |
|---|---|
| Regras para toda sessão | `AGENTS.md` (raiz e, quando houver, por pasta); o `CLAUDE.md` só importa o `AGENTS.md` |
| Escopo, roteiro e índice de decisões | `docs/PLANEJAMENTO.md` |
| Decisões com contexto | `docs/decisoes/` |
| Lições aprendidas | `docs/aprendizados.md` |
| Índices e fontes | `docs/indices/`, `docs/fontes/` |
| Método: identificação, valores, validações, quebras, fórmulas | `docs/METODOLOGIA.md` |
| Histórico de mudanças | `CHANGELOG.md` |

## Ambiente na nuvem

- **Rede:** os domínios do IBGE precisam estar liberados na política de rede do ambiente (A-004).
- **GitHub:** o `gh` não tem acesso ao GraphQL; use a API REST (`gh api repos/...`) para issues,
  rótulos e PRs (A-005).
- **Dependências:** instaladas pelo hook de início de sessão quando existir `pyproject.toml`.
