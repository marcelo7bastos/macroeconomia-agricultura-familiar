import importlib.util
import json
from pathlib import Path

import pytest

CAMINHO = Path(__file__).resolve().parents[1] / "docs/projetos/ipca-geral/publicar.py"


@pytest.fixture
def publicador():
    especificacao = importlib.util.spec_from_file_location("publicador_ipca", CAMINHO)
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def github(publicador, monkeypatch):
    estado = {
        "projetos": [],
        "issues": [
            {"number": 12, "html_url": "https://github.com/exemplo/repo/issues/12", "body": ""}
        ],
        "itens": set(),
        "vinculos": set(),
    }

    def argumento(args, nome):
        return args[args.index(nome) + 1]

    # Roteador do protocolo do CLI: um ramo por operação externa simulada.
    def responder(*args):  # noqa: PLR0911, PLR0912
        if args[:2] == ("api", "user"):
            return "usuario"
        if args[:2] == ("project", "list"):
            return json.dumps(
                {"projects": estado["projetos"], "totalCount": len(estado["projetos"])}
            )
        if args[:2] == ("api", "--paginate"):
            return json.dumps(estado["issues"][:1]) + "\n" + json.dumps(estado["issues"][1:])
        if args[:2] == ("project", "create"):
            projeto = {
                "id": "P_1",
                "number": 1,
                "title": argumento(args, "--title"),
                "url": "https://github.com/users/exemplo/projects/1",
            }
            estado["projetos"].append(projeto)
            estado["detalhe"] = {"closed": False, "shortDescription": "", "readme": ""}
            return json.dumps(projeto)
        if args[:2] == ("api", "graphql"):
            return json.dumps({"data": {"node": estado["detalhe"]}})
        if args[:2] == ("project", "edit"):
            for campo, opcao in [("shortDescription", "--description"), ("readme", "--readme")]:
                if opcao in args:
                    estado["detalhe"][campo] = argumento(args, opcao)
            return ""
        if args[:2] == ("project", "link"):
            estado["vinculos"].add(argumento(args, "--repo"))
            return ""
        if args[:2] == ("project", "item-list"):
            return json.dumps(
                {
                    "items": [{"content": {"url": url}} for url in estado["itens"]],
                    "totalCount": len(estado["itens"]),
                }
            )
        if args[:2] == ("project", "item-add"):
            estado["itens"].add(argumento(args, "--url"))
            return ""
        if args[:2] == ("issue", "create"):
            numero = 100 + len(estado["issues"])
            url = f"https://github.com/exemplo/repo/issues/{numero}"
            estado["issues"].append(
                {
                    "number": numero,
                    "html_url": url,
                    "body": Path(argumento(args, "--body-file")).read_text(encoding="utf-8"),
                }
            )
            return url
        if args[0] == "api" and "/issues/" in args[1]:
            numero = int(args[1].rsplit("/", 1)[-1])
            return json.dumps(next(i for i in estado["issues"] if i["number"] == numero))
        raise AssertionError(args)

    monkeypatch.setattr(publicador, "gh", responder)
    return estado


def test_publicacao_e_retomada_preservam_projeto_issues_e_edicoes(publicador, github):
    plano = publicador.carregar()
    publicador.publicar(plano)
    assert len(github["projetos"]) == 1
    assert len(github["issues"]) == 11
    assert len(github["itens"]) == 11
    assert plano["repositorio"] in github["vinculos"]
    github["detalhe"].update(shortDescription="Descrição humana", readme="README humano")
    github["issues"][1]["body"] += "\nRevisão humana."
    corpo = github["issues"][1]["body"]
    publicador.publicar(plano)
    assert len(github["projetos"]) == 1
    assert len(github["issues"]) == len(github["itens"]) == 11
    assert github["detalhe"]["readme"] == "README humano"
    assert github["detalhe"]["shortDescription"] == "Descrição humana"
    assert github["issues"][1]["body"] == corpo
    assert github["issues"][1]["html_url"] in github["issues"][2]["body"]


def test_retomada_completa_campos_e_vinculo_apos_criar_projeto(publicador, github):
    plano = publicador.carregar()
    publicador.gh("project", "create", "--title", plano["titulo"])
    publicador.publicar(plano)
    assert len(github["projetos"]) == 1
    assert github["detalhe"]["shortDescription"] == plano["descricao"]
    assert plano["url_plano"] in github["detalhe"]["readme"]
    assert plano["repositorio"] in github["vinculos"]


def test_listagem_incompleta_nao_cria_copias(publicador, monkeypatch):
    monkeypatch.setattr(publicador, "gh", lambda *args: '{"projects": [], "totalCount": 2}')
    with pytest.raises(RuntimeError, match="Listagem incompleta"):
        publicador.listar("list", "projects", "--owner", "exemplo")


def test_simulacao_nao_chama_github(publicador, monkeypatch, capsys):
    def proibido(*args):
        raise AssertionError("A simulação tentou acessar o GitHub")

    monkeypatch.setattr(publicador, "gh", proibido)
    monkeypatch.setattr("sys.argv", [str(CAMINHO)])
    publicador.main()
    assert "10 tarefas" in capsys.readouterr().out


def test_credencial_especifica_so_e_usada_no_processo_filho(publicador, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "integracao-de-teste")
    monkeypatch.setenv("GH_PROJECTS_TOKEN", "projects-de-teste")
    chamadas = []

    def executar(args, **opcoes):
        chamadas.append(opcoes)
        return publicador.subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.setattr(publicador.subprocess, "run", executar)
    assert publicador.gh("api", "user") == "ok"
    assert chamadas[0]["env"]["GH_TOKEN"] == "projects-de-teste"
    assert publicador.os.environ["GH_TOKEN"] == "integracao-de-teste"
