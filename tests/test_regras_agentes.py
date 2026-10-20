import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _versionados(nome: str) -> list[Path]:
    saida = subprocess.run(
        ["git", "ls-files", f"*{nome}", nome], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout
    return [RAIZ / linha for linha in sorted(set(saida.split())) if Path(linha).name == nome]


def test_todo_claude_md_so_importa_o_agents_md_ao_lado():
    # A-006: as regras ficam só no AGENTS.md; o CLAUDE.md ao lado contém apenas o import.
    arquivos = _versionados("CLAUDE.md")
    assert RAIZ / "CLAUDE.md" in arquivos
    for arquivo in arquivos:
        assert arquivo.read_text(encoding="utf-8").strip() == "@AGENTS.md", arquivo
        assert (arquivo.parent / "AGENTS.md").is_file(), arquivo
