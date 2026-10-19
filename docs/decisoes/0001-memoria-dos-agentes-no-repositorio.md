# 0001. Memória dos agentes no próprio repositório

- **Situação:** aceita
- **Data:** 2026-10-19
- **Issue/PR:** #20

## Contexto

O projeto quer aprendizado contínuo dos agentes de IA. O desenvolvimento acontece principalmente em
sessões do Claude Code na nuvem, que rodam em containers descartados ao fim da sessão: nada fora do
git sobrevive. O projeto já tem documentação viva (`AGENTS.md`, `docs/PLANEJAMENTO.md`, issues).

## Decisão

A memória de longo prazo dos agentes é o próprio repositório:

- `AGENTS.md` (raiz e por pasta): regras carregadas em toda sessão;
- `docs/aprendizados.md`: registro de lições, promovidas para teste, validação, regra ou ficha;
- `docs/decisoes/`: decisões com contexto;
- `docs/indices/` e `docs/fontes/`: conhecimento sobre índices e fontes;
- `tests/` e validações: a forma mais forte de memória, porque é verificada a cada execução.

Toda mudança em regras ou decisões passa por PR revisado pelo mantenedor.

## Alternativas consideradas

- **[ai-memory](https://github.com/akitaonrails/ai-memory)** (servidor de memória com wiki em
  markdown e captura por hooks): resolve continuidade entre agentes, máquinas e pessoas. Exige um
  servidor persistente fora do container, acessível pela política de rede do ambiente, e cria uma
  segunda fonte de verdade, escrita automaticamente e sem revisão, ao lado do `PLANEJAMENTO.md`.
  O custo não se paga num projeto com um mantenedor e um agente.
- **Memória nativa do Claude Code** (arquivos de memória do usuário): fica na máquina ou sessão,
  não é compartilhada nem versionada com o projeto.

## Consequências

- Qualquer agente ou pessoa lê a mesma memória, pelo GitHub, sem infraestrutura.
- Aprender exige um passo explícito (`/aprender`, `/fechar-etapa`); não há captura automática.
- Reavaliar se o projeto passar a ter vários colaboradores, alternância frequente entre agentes
  diferentes ou trabalho local frequente em várias máquinas.
