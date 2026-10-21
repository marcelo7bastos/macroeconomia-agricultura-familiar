# 0007. Marts versionados só em CSV

- **Situação:** aceita (escolha do mantenedor na #8)
- **Data:** 2026-10-20
- **Issue/PR:** #8; reavaliação na #55

## Contexto

O PLANEJAMENTO (seção 6) previa os marts em parquet e CSV em `data/marts/`, lidos pelo Power BI
pelas URLs do raw do GitHub. Os marts do IPCA-15 têm cerca de 150 mil linhas por arquivo. Cada
atualização mensal regrava os arquivos inteiros. No git, um CSV ordenado muda só nas linhas novas
ou revistas, e o histórico cresce pouco; um parquet é binário e entra inteiro a cada mês (cerca de
12 MB por mês nos arquivos grandes).

## Decisão

- Os marts ficam versionados **só em CSV**: UTF-8, separador vírgula, ponto decimal, linhas em
  ordem fixa e valores calculados arredondados (6 casas no índice e nas contribuições; 4 nos
  acumulados, na participação no grupo e na sazonalidade; 2 na difusão). Os valores oficiais
  passam como publicados.
- O parquet continua existindo só no staging, para uso local.
- O dicionário de dados (`data/marts/README.md`) é gerado do código; um teste exige que os
  arquivos versionados sejam os que o pipeline produz.

## Alternativas consideradas

- **CSV e parquet**, como no PLANEJAMENTO: o parquet dobra o espaço e faz o histórico do git
  crescer cerca de 12 MB por mês.
- **Só parquet:** menor e tipado, mas sem diff legível no GitHub e com o mesmo crescimento do
  histórico.
- **Parquet fora do git** (release, GitHub Pages ou LFS): fica para a #55, se o Power BI ou o site
  precisarem.

## Consequências

- O Power BI lê CSV; o README traz como ler no Power Query (delimitador, UTF-8, cultura en-US).
- Tipos (datas, inteiros) não vêm no arquivo; o dicionário diz o que cada coluna é.
- Reavaliar na #55 se a leitura ficar lenta, se um consumidor precisar de tipos ou se os CSVs
  passarem de ~50 MB.
