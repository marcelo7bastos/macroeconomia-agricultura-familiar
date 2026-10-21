# Publicação das explicações no GitHub Pages

O portal é estático e público; não exige login para ler dados e gráficos. Não é um site Quarto.
A fonte do Pages é a branch `gh-pages`, pasta `/`. A `main` conserva código, dados e documentos;
a branch de publicação contém somente o artefato do site e mantém histórico próprio de commits.

- [Entrada do portal](https://marcelo7bastos.github.io/macroeconomia-agricultura-familiar/).
- [IPCA geral](https://marcelo7bastos.github.io/macroeconomia-agricultura-familiar/docs/gestao/ipca.html).
- [IPCA-15](https://marcelo7bastos.github.io/macroeconomia-agricultura-familiar/docs/gestao/ipca15.html).
- Relatórios técnicos: `docs/transformacoes/ipca.html` e `ipca15.html` no mesmo site.

## Gerar e conferir

Na raiz do repositório:

```bash
uv run --locked python -m macroaf.relatorios.gestao
uv run --locked pytest tests/test_gestao.py -q
uv run --locked python -m macroaf.relatorios.site --destino /tmp/site-ipca
```

O destino precisa estar vazio. O empacotador copia documentos, marts, metadados e referências;
não publica raw, `.git`, variáveis de ambiente ou credenciais. Os HTMLs gerenciais incorporam
seu recorte de dados e não dependem de CDN nem da API do IBGE ao navegar.
Dados ausentes permanecem ausentes; a publicação é bloqueada se o CSV divergir do hash nos metadados.

## Automação após o merge

O workflow `Publicar explicações no Pages` (`pages.yml`) executa após mudanças pertinentes na
`main`, após a conclusão bem-sucedida de `Atualização dos dados`, ou por `workflow_dispatch`.
O gatilho `workflow_run` cobre commits do bot, que não disparam outros workflows de push.
Ele confere a explicação, monta o site, atualiza somente `gh-pages` e solicita o build via API.
Push com `GITHUB_TOKEN` sozinho não inicia build do Pages; a solicitação explícita é necessária.

São necessárias permissões `contents: write` e `pages: write`, além do Pages habilitado na fonte
indicada. A criação inicial do site e da branch é feita uma vez por um administrador autorizado.
O workflow ainda precisa estar na `main` para suas execuções automáticas; publicar a prévia
não implica realizar merge de código ou dispensar a revisão do mantenedor.

## Conferir o resultado e recuperar

Confirme o sucesso do workflow, do build do Pages e o endereço público, incluindo os dois índices,
filtros e ligação aos relatórios técnicos. O site representa uma publicação, não uma API em tempo
real. A data de coleta aparece em cada página; alterações de documentação não atualizam essa data.

Se o build falhar, o site anterior continua sendo a referência até uma implantação concluída.
Consulte o log, corrija e reexecute `Publicar explicações no Pages`. Para voltar a uma versão,
use o histórico de `gh-pages` e publique um commit de restauração, preservando a rastreabilidade.
O estado efetivamente implantado e os testes desta primeira publicação estão registrados na
issue #59 e no PR de entrega vinculado a ela.
