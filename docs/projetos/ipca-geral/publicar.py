"""Publica o plano no GitHub Projects; sem --aplicar, apenas valida e mostra as tarefas."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

CAMINHO = Path(__file__).with_name("tarefas.json")
LIMITE_LISTAGEM = 1000


def gh(*argumentos):
    ambiente = None
    if os.environ.get("GH_PROJECTS_TOKEN"):
        ambiente = os.environ.copy()
        ambiente["GH_TOKEN"] = ambiente["GH_PROJECTS_TOKEN"]
    processo = subprocess.run(
        ["gh", *argumentos], capture_output=True, text=True, check=False, env=ambiente
    )
    if processo.returncode:
        raise RuntimeError(processo.stderr.strip() or "GitHub CLI terminou com erro.")
    return processo.stdout


def carregar():
    plano = json.loads(CAMINHO.read_text(encoding="utf-8"))
    vistos = set()
    for tarefa in plano["tarefas"]:
        if tarefa["id"] in vistos or not set(tarefa["dependencias"]) <= vistos:
            raise ValueError(f"Tarefa repetida ou dependências fora de ordem: {tarefa['id']}")
        if not tarefa["aceite"]:
            raise ValueError(f"Tarefa sem aceite: {tarefa['id']}")
        vistos.add(tarefa["id"])
    return plano


def listar(tipo, chave, *argumentos):
    dados = json.loads(
        gh("project", tipo, *argumentos, "--limit", str(LIMITE_LISTAGEM), "--format", "json")
    )
    if dados.get("totalCount", LIMITE_LISTAGEM + 1) > len(dados[chave]):
        raise RuntimeError("Listagem incompleta; interrompido para não duplicar projetos ou itens.")
    return dados[chave]


def listar_issues(repositorio):
    # gh api --paginate devolve um array JSON por página nesta versão do CLI.
    texto = gh("api", "--paginate", f"repos/{repositorio}/issues?state=all&per_page=100")
    decodificador = json.JSONDecoder()
    issues = []
    while texto.strip():
        pagina, fim = decodificador.raw_decode(texto.lstrip())
        issues.extend(i for i in pagina if "pull_request" not in i)
        texto = texto.lstrip()[fim:]
    return issues


def corpo(plano, tarefa, existentes):
    dependencias = [existentes[codigo]["html_url"] for codigo in tarefa["dependencias"]]
    linhas = [
        f"<!-- projeto-ipca-geral:{tarefa['id']} -->",
        f"Referência: #{plano['issue_referencia']} (não encerra a frente inteira).",
        f"Prioridade: {tarefa['prioridade']}. Situação inicial: backlog.",
        "",
        "## Escopo",
        tarefa["escopo"],
        "",
        "## Dependências",
        *([f"- {url}" for url in dependencias] or ["- Nenhuma."]),
        "",
        "## Critérios de aceite",
        *[f"- [ ] {item}" for item in tarefa["aceite"]],
        "",
        f"Plano completo: {plano['url_plano']}",
        "",
        "Uma tarefa por branch e PR; revisão metodológica e verificações antes do merge.",
    ]
    return "\n".join(linhas) + "\n"


def preparar_projeto(plano, projeto, referencia):
    dono, repositorio = plano["proprietario"], plano["repositorio"]
    numero = str(projeto["number"])
    consulta = """query($id: ID!) {
        node(id: $id) { ... on ProjectV2 { closed shortDescription readme } }
    }"""
    detalhe = json.loads(
        gh("api", "graphql", "-f", f"query={consulta}", "-f", f"id={projeto['id']}")
    )["data"]["node"]
    if detalhe is None or detalhe["closed"]:
        raise RuntimeError("Projeto inacessível ou fechado; publicação interrompida.")
    edicoes = []
    if not detalhe["shortDescription"]:
        edicoes.extend(["--description", plano["descricao"]])
    if not detalhe["readme"]:
        edicoes.extend(
            ["--readme", f"Plano: {plano['url_plano']}\n\nReferência: {referencia['html_url']}"]
        )
    if edicoes:
        gh("project", "edit", numero, "--owner", dono, *edicoes)
    # Repor o vínculo é aditivo e também completa uma publicação interrompida após criar o projeto.
    gh("project", "link", numero, "--owner", dono, "--repo", repositorio)
    return numero


def publicar(plano):
    dono, repositorio = plano["proprietario"], plano["repositorio"]
    # Leituras antes de qualquer mutação: rede, autenticação, Projects e issue de referência.
    gh("api", "user", "--jq", ".login")
    projetos = listar("list", "projects", "--owner", dono, "--closed")
    issues = listar_issues(repositorio)
    referencia = next((i for i in issues if i["number"] == plano["issue_referencia"]), None)
    if referencia is None:
        raise RuntimeError(f"Issue de referência #{plano['issue_referencia']} não encontrada")
    correspondentes = [p for p in projetos if p["title"] == plano["titulo"]]
    if len(correspondentes) > 1:
        raise RuntimeError("Mais de um projeto com o mesmo título; não foi escolhida uma cópia.")
    if correspondentes:
        projeto = correspondentes[0]
        if projeto.get("closed"):
            raise RuntimeError("O projeto existente está fechado; nenhuma alteração foi feita.")
    else:
        projeto = json.loads(
            gh("project", "create", "--owner", dono, "--title", plano["titulo"], "--format", "json")
        )
    numero = preparar_projeto(plano, projeto, referencia)
    itens = listar("item-list", "items", numero, "--owner", dono)
    urls = {i.get("content", {}).get("url") for i in itens}

    def adicionar(url):
        if url not in urls:
            gh("project", "item-add", numero, "--owner", dono, "--url", url)
            urls.add(url)

    adicionar(referencia["html_url"])
    existentes = {}
    for tarefa in plano["tarefas"]:
        marcador = f"<!-- projeto-ipca-geral:{tarefa['id']} -->"
        candidatas = [i for i in issues if marcador in (i.get("body") or "")]
        if len(candidatas) > 1:
            raise RuntimeError(f"Issues repetidas para {tarefa['id']}; publicação interrompida.")
        if candidatas:
            issue = candidatas[0]
        else:
            with tempfile.TemporaryDirectory(prefix="projeto-ipca-") as pasta:
                caminho = Path(pasta) / "issue.md"
                caminho.write_text(corpo(plano, tarefa, existentes), encoding="utf-8")
                url = gh(
                    "issue",
                    "create",
                    "--repo",
                    repositorio,
                    "--title",
                    tarefa["titulo"],
                    "--body-file",
                    str(caminho),
                    "--label",
                    "backlog",
                ).strip()
            numero_issue = url.rstrip("/").rsplit("/", 1)[-1]
            issue = json.loads(gh("api", f"repos/{repositorio}/issues/{numero_issue}"))
            issues.append(issue)
        existentes[tarefa["id"]] = issue
        adicionar(issue["html_url"])
        print(f"{tarefa['id']}: {issue['html_url']}", flush=True)
    print(f"Projeto: {projeto['url']}", flush=True)
    print("Na interface, selecione layout Board e agrupamento por Status.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--aplicar", action="store_true", help="Cria/reutiliza projeto, issues e itens no GitHub."
    )
    args = parser.parse_args()
    plano = carregar()
    if not args.aplicar:
        print(f"Simulação: {plano['titulo']} ({len(plano['tarefas'])} tarefas)")
        for tarefa in plano["tarefas"]:
            print(
                f"{tarefa['id']} {tarefa['prioridade']}: {tarefa['titulo']}; "
                f"depende de {tarefa['dependencias']}"
            )
        return
    try:
        publicar(plano)
    except (RuntimeError, StopIteration) as erro:
        raise SystemExit(
            f"Publicação não concluída: {erro}. Reexecute após resolver o acesso."
        ) from erro


if __name__ == "__main__":
    main()
