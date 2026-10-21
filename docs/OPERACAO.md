# Operação e desenvolvimento

Instruções para IPCA-15 e IPCA, revisadas em 20/10/2026. Execute os comandos na raiz do repositório.
Os nomes legados `transform.ipca15` e `validate.ipca15` aceitam os dois índices por configuração.
Sem `--indice`, o padrão é `ipca15`. Não existe `--indice todos` no CLI do pipeline;
`todos` é uma opção do workflow.

## Preparar o ambiente e verificar o código

Requer Git, acesso às APIs do IBGE e [uv](https://docs.astral.sh/uv/). O projeto usa Python 3.12.

```bash
uv sync --all-groups --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest -v --durations=15
```

Os testes de publicação usam o raw versionado, sem precisar extrair novamente. A consulta real
à API fica separada no workflow `API do IBGE`; instabilidade da fonte não é falha de transformação.
Se o ambiente impedir a escrita no cache padrão do uv, configure `UV_CACHE_DIR` para uma pasta
gravável. Isso não muda as dependências do projeto.

## Atualizar do IBGE até os CSVs

```bash
uv run --locked python -m macroaf.extract.atualizar --indice ipca --verificar
uv run --locked python -m macroaf.pipeline --indice ipca
uv run --locked python -m macroaf.pipeline --indice ipca15
```

`--verificar` consulta metadados e informa pendências; não publica dados. O pipeline consulta
as tabelas abertas e revisa os três meses mais recentes. Sem mudança no raw, termina sem
republicar. Com novidade, refaz harmonização, valida, publica os marts e gera as páginas.
Não execute dois publicadores simultaneamente: índices distintos compartilham manifesto e metadados.

Para republicar após alteração de método ou recuperar uma execução local interrompida:

```bash
uv run --locked python -m macroaf.pipeline --indice ipca --forcar
```

`--forcar` refaz a publicação mesmo sem novidade; continua consultando a API e não ignora
validações. Para reconstrução sem rede a partir do raw existente, use as etapas locais abaixo.

## Executar por etapas

Exemplo para IPCA; troque apenas `--indice ipca` por `--indice ipca15` para o piloto:

```bash
uv run --locked python -m macroaf.extract.atualizar --indice ipca
uv run --locked python -m macroaf.transform.ipca15 --indice ipca
uv run --locked python -m macroaf.validate.ipca15 --indice ipca
uv run --locked python -m macroaf.transform.harmonizacao --indice ipca
uv run --locked python -m macroaf.marts.publicar --indice ipca
uv run --locked python -m macroaf.relatorios.transformacoes --indice ipca
uv run --locked python -m macroaf.relatorios.revisao --indice ipca
```

Só a extração exige rede; as etapas seguintes consomem o raw. O publicador recompõe seus dados
e validações antes de gravar: executar apenas a transformação não atualiza os CSVs publicados.
Confira `git diff` e rode a suíte antes de enviar alterações. Não edite CSVs gerados ou HTML à mão.

## Atualização no GitHub Actions

O workflow **Atualização dos dados** consulta diariamente às **09:23 de Brasília** (12:23 UTC).
Consulta diária não significa novo dado diário. Em **Actions → Atualização dos dados → Run workflow**,
use a branch `main`, selecione `ipca`, `ipca15` ou `todos` e marque `forcar` só se precisar republicar.

Os jobs são sequenciais e leem a `main` atual; o grupo de concorrência impede execuções simultâneas
do mesmo workflow. Uma falha não autoriza publicar o índice afetado; o outro job pode executar.
O commit/push de dados só acontece após o pipeline e os testes passarem, se houver mudança.
As permissões e proteções da `main` precisam permitir esse push. A configuração estar na `main`
não comprova uma execução bem-sucedida: confira os logs e o commit resultante.

Para repetir uma checagem de PR, abra **Checks**, acesse a execução e use **Re-run failed jobs**
ou **Re-run all jobs**. Um novo push no PR dispara outra execução. Reexecutar uma execução antiga
testa seu commit antigo; confira o SHA antes de interpretar o resultado.

## Falhas e recuperação

| Situação | O que conferir / fazer |
|---|---|
| API fora do ar, 429 ou 5xx | O cliente já tenta novamente; persistindo, conferir rede e repetir depois |
| HTTP 400 do SIDRA | Erro definitivo; conferir URL, dimensões e limite, sem retentar indefinidamente |
| Referência um mês à frente do detalhe aberto | Divulgação parcial: o pipeline aguarda, sai com 0 e a próxima execução tenta completar |
| Catálogo divergente, saída 2 | Conferir metadados e possível nova POF; seguir a issue #27, sem editar datas para ocultar o problema |
| Validação ou conferência falhou, saída 1 | Localizar a regra e diagnosticar contra o raw; não ampliar tolerâncias nem copiar exceções |
| Interrupção após baixar dados | Conferir alterações parciais e executar novamente com `--forcar`; preservar revisões e decisões |
| Pytest parece parado | Após 5 minutos o log imprime a pilha; distinguir processamento de geração de diff e investigar o teste indicado |

A publicação local escreve vários arquivos e não é uma transação única. As verificações bloqueiam
a gravação quando detectam problemas nos dados, mas um erro de I/O posterior pode deixar arquivos
parciais. O estado final só deve ser enviado após a execução inteira e os testes passarem.

## Comparações numéricas

O critério de 0,001 ponto percentual é inclusivo e vale somente para acumulados calculados e
contribuições na comparação de publicações entre ambientes. Oficiais, códigos, textos, datas,
estrutura e ausentes são exatos; os demais campos seguem os comparadores dos testes.
Isso não substitui os limites analíticos das validações contra o IBGE nem muda as casas publicadas.
Cada hash é conferido contra o próprio CSV. Consulte [Metodologia, seção 12](METODOLOGIA.md#12-marts-8).

## Explicações e site público

Após atualizar os marts, gere `uv run python -m macroaf.relatorios.gestao` (os dois índices)
ou acrescente `--indice ipca` / `--indice ipca15`. O workflow de dados faz isso para o índice
processado. A [publicação no Pages](PUBLICACAO.md) usa outro workflow e outra branch, para
não misturar a gravação dos dados com a implantação do site.
