import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


def _versionados(nome: str) -> list[Path]:
    if not (RAIZ / ".git").exists():
        pytest.skip("fora de um repositório git: não há lista de arquivos versionados")
    saida = subprocess.run(
        ["git", "ls-files", f"*{nome}", nome], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout
    return [RAIZ / linha for linha in sorted(set(saida.splitlines())) if Path(linha).name == nome]


def test_todo_claude_md_so_importa_o_agents_md_ao_lado():
    # A-006: as regras ficam só no AGENTS.md; o CLAUDE.md ao lado contém apenas o import.
    arquivos = _versionados("CLAUDE.md")
    assert RAIZ / "CLAUDE.md" in arquivos
    for arquivo in arquivos:
        assert arquivo.read_text(encoding="utf-8").strip() == "@AGENTS.md", arquivo
        assert (arquivo.parent / "AGENTS.md").is_file(), arquivo


def test_todo_agents_md_tem_claude_md_ao_lado():
    # A-006: sem o CLAUDE.md que importa, o Claude Code ignora a regra da pasta sem avisar.
    arquivos = _versionados("AGENTS.md")
    assert RAIZ / "AGENTS.md" in arquivos
    claude = set(_versionados("CLAUDE.md"))
    for arquivo in arquivos:
        assert arquivo.parent / "CLAUDE.md" in claude, arquivo
