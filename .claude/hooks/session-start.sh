#!/bin/bash
# Início de sessão: instala dependências (só na nuvem) e lembra as lições mais recentes.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

# Dependências: só em sessões na nuvem, a partir do uv.lock (sem reescrevê-lo), como no CI.
if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ] && [ -f pyproject.toml ]; then
  uv sync --all-groups --frozen >&2
fi

# O texto impresso aqui entra no contexto da sessão.
if [ -f docs/aprendizados.md ]; then
  recentes=$(grep -E '^### A-[0-9]+' docs/aprendizados.md | head -n 5 | sed 's/^### /- /' || true)
  if [ -n "$recentes" ]; then
    echo "Lições mais recentes em docs/aprendizados.md (leia as que tocarem a tarefa):"
    echo "$recentes"
  fi
fi
