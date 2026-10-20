# Aprendizados

Registro do que os agentes (e as pessoas) aprenderam trabalhando no projeto. É a memória de longo
prazo dos agentes: sessões na nuvem são descartadas, o git fica.

## Como funciona

1. Uma descoberta não óbvia vira entrada aqui pela skill `/aprender`.
2. Cada lição é **promovida** para a forma mais forte que couber:

   | Força | Destino | Quando |
   |---|---|---|
   | 1 | teste automatizado (`tests/`) | dá para verificar no código; bug vira teste de regressão |
   | 2 | validação no pipeline (`src/macroaf/validate/`) | é propriedade dos dados |
   | 3 | regra no `AGENTS.md` (raiz ou de pasta) | é conduta que vale em toda sessão |
   | 4 | ficha (`docs/indices/`, `docs/fontes/`) | é conhecimento sobre um índice ou fonte |

3. Mudanças em `AGENTS.md` e em decisões passam por PR revisado pelo mantenedor.
4. Se a lição muda como os dados são tratados, a regra resultante vai também para
   [`METODOLOGIA.md`](METODOLOGIA.md), citando o A-NNN.
5. O hook de início de sessão mostra os títulos das cinco lições mais recentes.

Entradas novas vão **no topo** do registro, com numeração crescente (`A-NNN`). Uma lição que deixou
de valer não é apagada: ganha a linha `**Substituída por:** A-NNN`.

## Registro

### A-035 · 2026-10-20 · IPCA: inconsistências oficiais precisam de contagens e origens próprias
- **Contexto:** extração integral e validação do IPCA (#12), confronto com respostas oficiais.
- **O que aconteceu:** na 2938, os grupos somam 100,0999 em 2010-07 e 550 passos anuais excedem
  o limite analítico. Separadamente,239 acumulados anuais em 53 categorias divergem da composição
  desde janeiro; duas categorias desse conjunto não têm passo isolado fora do limite. A1419
  publica 13 zeros em 12 meses de Depilação (dez/2012–dez/2013), incompatíveis com as mensais.
  A1737 publica 2,46 em 6 meses emjan/2010 contra 2,219154 pela composição mensal.
- **Lição:** não ampliar tolerâncias nem copiar exceções do IPCA-15. Contar passos e marcar
  meses anuais errados por critérios separados. Preservar o oficial no fato; usar calculado
  com origem explícita apenas nos casos documentados e aferidos por identidade.
- **Promovida para:** `excecoes_validacao_ipca.csv`, `diagnostico_acumulado_ano_ipca.csv`, testes
  independentes da lista 239, `VALIDACAO_CATEGORIA` para 12 meses e `METODOLOGIA.md`14.

### A-034 · 2026-10-20 · Categoria listada pode não ter coleta em todo o período da POF
- **Contexto:** tabela 1419 do IPCA, extração integral (#12).
- **O que aconteceu:**952 observações de 18 categorias têm mensal, anual e peso simultaneamente
  ausentes. Oito começam em 2014-01; dez em 2018-05. Quatro existiam na POF anterior, mas voltam
  depois de uma lacuna. Emendar só pelo código/id criaria uma continuidade falsa.
- **Lição:** preservar o raw e excluir do fato apenas linhas com as três medidas fundamentais
  ausentes. Aferir a cobertura esperada independentemente no raw para detectar perda de linhas
  ativas e zeros fabricados. Não emendar categorias com meses observados não adjacentes.
- **Promovida para:** `montar_fato`, `Configuracao.indisponiveis`, `validar_continuidade`,
  `propor_mapa`, testes reais do IPCA e `METODOLOGIA.md`14.

### A-033 · 2026-10-20 · O hífen do SIDRA é zero absoluto, confirmado na fonte
- **Contexto:** erro de transformação da variável 2265 do IPCA (#12).
- **O que aconteceu:** a 1419 traz 13 valores `-` para Depilação. A ajuda oficial
  https://apisidra.ibge.gov.br/home/ajuda define `-` como zero absoluto e `...` como indisponível.
- **Lição:** converter `-` em 0,0, mantendo o literal original no raw. Isso não atesta que a série
  publicada está correta: zeros também precisam passar nas identidades contábeis.
- **Promovida para:** `converter_valor`, teste de regressão e `METODOLOGIA.md`4 e 14.

### A-032 · 2026-10-20 · IPCA exige composição no histórico anterior a julho/2006
- **Contexto:** planejamento da fonte IPCA cheio (#12), levantamento nas APIs oficiais.
- **O que aconteceu:** 655, 656 e 657 cobrem os mesmos 83 meses (ago/1999–jun/2006) e categorias,
  publicando respectivamente variação, peso e acumulado no ano. O catálogo atual admite apenas
  tabelas sucessivas sem sobreposição e uma POF por tabela. A referência 1737 começa em 1979-12,
  antes do detalhe; os intervalos ausentes de 12 meses também diferem dos do IPCA-15.
- **Lição:** preparar primeiro 2938/1419/7060 desde julho/2006 e separar a extensão histórica.
  Projetar a composição das tabelas complementares antes de ativá-las, preservar a cobertura
  original da referência e validar no intervalo pertinente. Trocar apenas os IDs do IPCA-15
  não implementa essas diferenças.
- **Promovida para:** ficha `docs/indices/ipca.md` e plano `docs/projetos/ipca-geral.md`, com
  tarefas específicas de composição, cobertura, perfil de ausentes e regressão.

### A-031 · 2026-10-20 · Diferença numérica entre CPUs e diff gigante ocultavam a falha
- **Contexto:** CI do PR #57 parado por 20 minutos no teste de publicação (#9).
- **O que aconteceu:** a pilha apontou `difflib` ao explicar uma igualdade de CSVs de vários MB.
  Desativando as otimizações de CPU do NumPy, reproduzimos diferenças em 13 linhas de acumulados
  e 38 de contribuições, nas últimas casas arredondadas; com `--assert=plain`, a falha apareceu
  em 9,94 s. O processamento terminava: a explicação da diferença é que consumia o tempo.
- **Lição:** por regra do mantenedor, comparar acumulados de origem `calculado` e contribuições
  calculadas com diferença absoluta máxima inclusiva de 0,001 p.p., sem tolerância relativa.
  Preservar igualdade exata nos oficiais, códigos, datas, textos, estrutura e valores ausentes.
  Informar apenas a primeira diferença, com arquivo, linha e coluna; não gerar diff integral.
- **Promovida para:** `tests/comparar_publicacao.py`, `tests/test_comparar_publicacao.py`, teste
  de publicação em `tests/test_marts.py` e `METODOLOGIA.md` 12. A regra não muda as fórmulas,
  casas publicadas nem as validações contra o IBGE da seção 6.

### A-030 · 2026-10-20 · Fixtures de módulo repetem a preparação entre arquivos
- **Contexto:** investigação do CI intermitente no PR #57 (#9).
- **O que aconteceu:** no commit 644b959, a suíte chamou `montar_fato` 13 vezes. Um experimento
  local compartilhando a preparação das fixtures e o HTML reduziu as chamadas para 4 e o tempo
  de 99,34 s para 77,67 s. Isso mede trabalho repetido, sem comprovar a causa do travamento no CI.
- **Lição:** compartilhar os dados básicos por sessão e entregar cópias por módulo; manter
  independentes a publicação completa e as validações de dados alterados. O ganho de tempo não
  implica redução de memória, pois os dados compartilhados permanecem vivos durante a sessão.
- **Promovida para:** `tests/conftest.py` e fixture `pagina_gerada` em
  `tests/test_relatorio_transformacoes.py`.

### A-029 · 2026-10-20 · No dia da divulgação, um mês de defasagem não é troca de POF
- **Contexto:** atualização automática (#9), revisão do `revisor-metodologico`.
- **O que aconteceu:** a extração trata tabela de dados aberta atrás da referência (3065) como
  sinal de troca de tabela (código 2). No dia da divulgação, as duas podem ser atualizadas em
  horários diferentes; uma rotina diária às 09:23 daria falso alarme de POF nova, com workflow
  vermelho e e-mail. Na mesma revisão: metadados podem mudar sem mês novo nem revisão, e o pipeline
  diria "nada novo" deixando o raw alterado sem republicar.
- **Lição:** defasagem de exatamente um mês é divulgação em andamento (aguarda, saída 0); maior é
  troca. Toda mudança no raw, inclusive de metadados, conta como novidade.
- **Promovida para:** `AguardandoDivulgacao` e `Relatorio.houve_mudanca` em
  `macroaf.extract.atualizar`; testes `test_referencia_um_mes_a_frente_e_divulgacao_em_andamento`,
  `test_metadados_alterados_contam_como_mudanca` e `test_ibge_ainda_divulgando_nao_e_falha`;
  `METODOLOGIA.md` 1.

### A-028 · 2026-10-20 · Mart publicado do zero esconde estado e marcas
- **Contexto:** marts (#8), revisão do `revisor-metodologico`.
- **O que aconteceu:** duas falhas que os testes não pegavam. (1) O teste de "marts em dia"
  publicava num diretório vazio; o histórico de mudanças de série (decisão 0006) depende da
  publicação anterior, então na primeira mudança real o teste falharia para sempre. (2) A
  sazonalidade marca a janela de 5 anos que contém mês de cesta variável, mas o mart levava só a
  marca do mês: 1.632 linhas de sazonalidade contaminada saíam com `cesta_variavel = 0`.
- **Lição:** artefato com estado acumulado se confere a partir do estado versionado, não do zero.
  Toda marca de qualidade de um indicador (cesta variável por janela, origem) tem coluna no mart.
- **Promovida para:** fixture `publicado` de `tests/test_marts.py` (copia o estado versionado);
  coluna `sazonalidade_cesta_variavel` e teste
  `test_marca_de_cesta_variavel_da_sazonalidade_chega_ao_mart`; `METODOLOGIA.md` 12.

### A-027 · 2026-10-20 · "Fecha #N" não fecha a issue
- **Contexto:** depois do merge dos PRs #49 a #52, as issues #41 a #44 continuaram abertas; o mesmo
  com #1 a #7, #20 e #22.
- **O que aconteceu:** o GitHub só fecha a issue no merge com as palavras-chave em inglês (close,
  closes, fix, fixes, resolve, resolves) e só se a base do PR for o branch padrão. "Fecha #N" vira
  só uma referência. Em PRs empilhados, nem a palavra certa fecha, porque a base não é a `main`.
- **Lição:** o PR cita `Closes #N (fecha #N)`; em PR empilhado, feche a issue à mão depois do merge.
- **Promovida para:** `AGENTS.md` (fluxo de trabalho); issues antigas fechadas à mão.

### A-026 · 2026-10-20 · Peso 0 com variação 0,00 é "não coletado"
- **Contexto:** difusão (#44), revisão do `revisor-metodologico`.
- **O que aconteceu:** na 1646 há 93 subitens com peso 0 (fora de safra, A-013); em 84 a variação
  publicada é exatamente 0,00 e em 9 vai de −26,54 a 10,04. Na difusão simples, contavam como "não
  subiu" e baixavam o geral em até 0,40 p.p.
- **Lição:** indicador que conta linhas não conta subitem com peso 0: a variação dele não informa
  preço. Generaliza A-013 e A-025 (linha sem informação mexendo no denominador).
- **Promovida para:** `montar_difusao` (coluna `subitens_peso_zero`); testes
  `test_difusao_simples_e_ponderada` e `test_difusao_real_entre_0_e_100_e_um_valor_por_mes`;
  `METODOLOGIA.md` 11.

### A-025 · 2026-10-20 · Linha excluída muda o denominador de quem fica
- **Contexto:** contribuições (#43), revisão do `revisor-metodologico`.
- **O que aconteceu:** os subitens in natura da 1646 saem da contribuição (A-013). A participação
  no grupo dos outros subitens do grupo 1 passou a ser dividida pela soma dos que sobraram, que não
  é a variação do grupo (razão de −5,9 a 5,5). O teste "soma 100%" passava por construção.
- **Lição:** indicador que exclui linhas precisa esvaziar ou marcar tudo o que usa a soma delas
  como denominador. Teste de "soma 100%" não basta: confira a soma contra o pai.
- **Promovida para:** `participacao_no_grupo` vazia onde falta contribuição no nível e grupo;
  testes `test_participacao_vazia_onde_falta_contribuicao_no_grupo` e
  `test_participacao_presente_soma_a_contribuicao_do_grupo`; `METODOLOGIA.md` 10.

### A-024 · 2026-10-20 · Escopo de exceção não é o mês do erro
- **Contexto:** acumulados por janela (#42), revisão do `revisor-metodologico`.
- **O que aconteceu:** para trocar o oficial pelo calculado onde a fonte errou, usei o escopo das
  exceções A-015. Mas a exceção de 2003-02..2003-03 cobre 2003-03 só porque a validação de um passo
  ancora no mês anterior; a 356 de 2003-03 está certa. Cerca de 100 valores oficiais corretos (91
  com cesta variável) viraram calculados. Na mesma conferência, a 356 da 1646 e da 1387, composta
  desde janeiro, diverge do índice em 638 linhas fora da cesta (até ~0,25 p.p.), mais que os 58
  casos de um passo da validação.
- **Lição:** exceção diz o que a validação aceita; erro publicado diz o que está errado. São
  colunas diferentes (`meses_com_erro_publicado`). Ruído sem erro identificado não autoriza trocar
  o oficial.
- **Promovida para:** coluna `meses_com_erro_publicado` (conferida ao carregar as exceções);
  testes `test_mes_que_so_falha_pela_ancora_fica_oficial` e
  `test_356_das_tabelas_antigas_fica_oficial_mesmo_com_ruido`; `METODOLOGIA.md` 6.5 e 9.

### A-023 · 2026-10-20 · O acumulado no ano do IBGE segue o código, não a série longa
- **Contexto:** índice encadeado por série longa (#41), conferido contra a 356 por categoria;
  revisão do `revisor-metodologico`.
- **O que aconteceu:** no ano da troca de POF, a 356 ancora janeiro pelo código (mesmo com id SIDRA
  novo); para código novo, começa no mês da troca, salvo 12 categorias da 1387 que o IBGE ancorou
  num antecessor de outro código (8101014 → 8104 e subitens; Peito de frango → Frango em pedaços;
  Queijo prato → Queijo), identificadas pelo janeiro implícito (2,88%, −12,47% e −3,65%, iguais ao
  acumulado de julho do antecessor). Com isso, 8 séries emendadas pela revisão com troca de código
  têm 356 "desde a troca", e 12 séries quebradas pelo projeto no meio do ano têm 356 que atravessa
  a quebra pelo código. Refina a A-017.
- **Lição:** a 356 só é acumulado no ano da série longa quando a série tem janeiro naquele ano e o
  código não mudou. Usá-la fora disso como "oficial primeiro" seria emenda silenciosa. As âncoras do
  IBGE são evidência de harmonização, para revisão humana.
- **Promovida para:** testes `test_acumulado_no_ano_atravessa_a_troca_quando_o_codigo_continua`,
  `test_codigo_novo_no_ano_da_troca_acumula_desde_a_troca`,
  `test_serie_quebrada_no_ano_da_troca_tem_356_que_atravessa_a_quebra` e
  `test_ancora_escolhida_pelo_ibge_na_troca_para_a_1387`; `METODOLOGIA.md` 8.2 e 8.3; regra a
  aplicar na #42; issue #48.

### A-022 · 2026-10-20 · Divisão permite comparar para trás, não seguir para a frente
- **Contexto:** revisão humana das propostas de harmonização (#6), observação do mantenedor sobre
  "Peixe" dividido em espécies na POF 2017-18.
- **O que aconteceu:** 116 propostas aceitas e 14 não aceitas; todas as não aceitas pediram
  investigação (issues #32 a #40). Para as divisões, o mantenedor observou que a soma das
  categorias novas ainda se compara com a antiga no passado, mas a antiga não continua no presente.
- **Lição:** divisão não aceita é quebra na série do subitem; uma comparação retroativa agregada é
  um produto à parte (a definir nas issues), nunca uma emenda. Decisão humana sempre cita a issue
  que a investiga.
- **Promovida para:** mapa (`situacao`, revisor e observação com a issue); `METODOLOGIA.md` 7.4;
  issues #32 a #40; teste `test_leite_pasteurizado_nao_emenda_no_longa_vida`.

### A-021 · 2026-10-19 · Busca de candidatos que ignora quem mantém o código esconde fusões
- **Contexto:** revisão do mapa de harmonização (#6) pelo `revisor-metodologico`.
- **O que aconteceu:** a busca só cruzava códigos que somem com códigos que aparecem. "Refrigerante"
  → "Refrigerante e água mineral" (mesmo código, id novo) saía como renomeação 1 para 1 e "Água
  mineral" como descontinuada; o revisor podia aprovar uma emenda que, na verdade, ampliou o
  escopo. O mesmo com "Frango" → "Frango inteiro" + "Frango em pedaços". Ao ampliar a busca, a
  ligação entre itens diferentes passou a parear "Refrigerante" em casa com "Refrigerante" fora de
  casa.
- **Lição:** categorias com o mesmo código e id novo entram na busca de candidatos; entre itens
  diferentes, só código extinto → código novo. A grafia igual com id novo também é proposta.
- **Promovida para:** `macroaf.transform.harmonizacao`; testes
  `test_fusao_com_categoria_que_mantem_o_codigo_aparece` e
  `test_mesmo_codigo_com_id_novo_nunca_emenda_sem_revisao`; `METODOLOGIA.md` 7.1; decisão 0005.

### A-020 · 2026-10-19 · Nem os subgrupos são totalmente estáveis entre POFs
- **Contexto:** mapa de harmonização (#6).
- **O que aconteceu:** grupos são idênticos em todas as trocas, mas o subgrupo `72` muda de id e
  de nome duas vezes ("Recreação, fumo e filmes" → "... e fotografia" → "Recreação e fumo"), o
  item `1117` Alimentos prontos some na 1387 e o item `7203` Fotografia e filmagem some na 7062.
- **Lição:** o planejamento dizia que até subgrupo a série sai direto; na prática subgrupos e itens
  passam pela mesma regra dos subitens.
- **Promovida para:** `macroaf.transform.harmonizacao` (todos os níveis no mapa);
  `METODOLOGIA.md` 7.3; `PLANEJAMENTO.md` 4.3.

### A-019 · 2026-10-19 · Similaridade de texto pareia nomes sem relação
- **Contexto:** primeira proposta do mapa de harmonização (#6).
- **O que aconteceu:** `difflib` com limite de 0,6 propôs "Melão" → "Telha", "Curso supletivo" →
  "Chuveiro elétrico" e 25 pares entre espécies de peixe diferentes (253 propostas ao todo).
- **Lição:** comparar palavras, não letras: contar as palavras do nome menor presentes no maior,
  sem palavras vazias, exigir mais da metade das do maior (ou todas as do menor) e o mesmo item;
  entre itens diferentes, só nome igual. Resultado: 115 propostas, plausíveis para revisão (algumas
  fracas, como "Óculos sem grau" → "Óculos de grau", ficam para o revisor rejeitar).
- **Promovida para:** `parentesco` em `macroaf.transform.harmonizacao`; teste
  `test_parentesco_de_nomes`; `METODOLOGIA.md` 7.1.

### A-018 · 2026-10-19 · Exceção estreita, contada e com limite empírico separado
- **Contexto:** revisão das validações (#5) pelo `revisor-metodologico`, com erros injetados.
- **O que aconteceu:** (1) exceções da 3065 cobriam o mês inteiro de todos os acumulados, e um
  erro injetado na 1118 e na 1120 de 2006-04 passava; (2) a sentinela "ao menos uma falha" não
  via correção parcial nem erro novo no escopo; (3) o limite empírico das tabelas antigas igual ao
  máximo observado deixava passar +0,10 num subitem da 1387; (4) janeiro tinha folga de 0,015 onde
  a identidade é exata; (5) a continuidade partia dos meses do raw, não do catálogo; (6) diferença
  não calculável era descartada em silêncio.
- **Lição:** exceção tem o escopo da justificativa (uma variável) e a contagem exata de falhas;
  limite empírico fica no p99,9, com o que passa dele listado como exceção contada; identidades
  exatas são validadas por igualdade; o esperado vem do catálogo e da classificação; diferença
  ausente é falha.
- **Promovida para:** `macroaf.validate.ipca15` e testes de erro injetado em
  `tests/test_validacao_ipca15.py`; `reference/limites_validacao_ipca15.csv`; `METODOLOGIA.md`
  6.1, 6.3 e 6.5.

### A-017 · 2026-10-19 · Categorias novas na troca de POF trazem acumulado herdado
- **Contexto:** calibração do acumulado no ano (#5), pelo `validador-dados`.
- **O que aconteceu:** na 1387 (ago/2006), categorias novas já vêm com acumulado no ano desde
  janeiro (ex.: 8104007 com variação -2,14 e acumulado 0,68), sem dados anteriores publicados; na
  1705 e na 7062 as novas começam com acumulado = variação do mês.
- **Lição:** não validar o acumulado no ano no primeiro mês de uma categoria nova; a série longa
  dessas categorias começa na troca de POF.
- **Promovida para:** regra de um passo da validação `acumulado_ano` (só valida com o mês
  anterior na mesma tabela); `METODOLOGIA.md` 6.1; pedido na #6.

### A-016 · 2026-10-19 · A 356 das tabelas antigas é mais ruidosa que o arredondamento
- **Contexto:** calibração do acumulado no ano (#5).
- **O que aconteceu:** na 1705 e na 7062 a 356 fecha com a 355 dentro do arredondamento; na 1646
  e na 1387 passa dele (até 0,02 no geral, que também difere da 356 da 3065 em 29 meses).
- **Lição:** nessas tabelas o limite é o máximo observado por nível, documentado como ruído da
  fonte; para o índice geral, a referência é a 3065.
- **Promovida para:** validação `acumulado_ano` (limite por nível); `METODOLOGIA.md` 6.3.

### A-015 · 2026-10-19 · O SIDRA publica erros pontuais
- **Contexto:** falhas de validação investigadas pelo `validador-dados` (#5), conferidas na API.
- **O que aconteceu:** 356 trocada ou repetida na 1646 (2003-02, 2004-07); pesos da 1387
  escalados por 1,000999 (2010-07/08); item 1115 da 1387 incoerente (2011-10/11); subitem 9101022
  da 1705 com 0,00 contrariando o peso (2014-07/09); acumulados 1118/1119 da 3065 que contradizem
  o próprio número-índice (2006-04, 2011-11, 2012-11).
- **Lição:** manter o dado publicado, explicar e listar como exceção do tipo `fonte`; cada exceção
  é sentinela: se o IBGE corrigir, o teste avisa.
- **Promovida para:** `reference/excecoes_validacao_ipca15.csv`; teste
  `test_toda_excecao_ainda_cobre_uma_falha`; `METODOLOGIA.md` 6.4 e 6.5.

### A-014 · 2026-10-19 · Tolerância é o limite analítico de arredondamento
- **Contexto:** calibração das validações (#5).
- **O que aconteceu:** tolerâncias fixas (0,01 p.p.) davam falsos positivos (1705, itens com
  variação grande e subitens de peso pequeno) e não diziam se a diferença era arredondamento.
- **Lição:** com variações em 2 casas e pesos em 4, o erro máximo de cada conta é calculável; a
  diferença é comparada com ele. Maior razão observada fora das exceções: 0,97.
- **Promovida para:** `macroaf.validate.ipca15`; `METODOLOGIA.md` 6.1.

### A-013 · 2026-10-19 · Cesta variável nos in natura da POF 1995-96 (tabela 1646)
- **Contexto:** falha sistemática da reconciliação na 1646 (#5), investigada pelo `validador-dados`.
- **O que aconteceu:** os itens 1103, 1105 e 1106 não reproduzem a média ponderada dos subitens
  (até 6,6 p.p.); os pesos dos subitens seguem o calendário de safra, há 93 pesos zero e o
  acumulado no ano dos subitens não fecha. O subgrupo 11 reconcilia pelos itens; na 1387 em diante
  o fenômeno some.
- **Lição:** na 1646, validar esses itens pelo nível acima e calcular contribuições a partir do
  item; exceção estrutural, não tolerância.
- **Promovida para:** exceções `estrutural` em `reference/excecoes_validacao_ipca15.csv`; teste
  `test_sem_excecoes_os_erros_da_fonte_aparecem`; `METODOLOGIA.md` 6.2; ficha; pedido na #7.

### A-012 · 2026-10-19 · Mesmo código IBGE, id SIDRA diferente entre POFs
- **Contexto:** revisão da `dim_classificacao` (#4).
- **O que aconteceu:** 87 códigos IBGE têm `codigo_sidra` diferente entre tabelas, sempre com o
  nome alterado (ex.: `1101073` é 7180 na 1646/1387 e 12222 na 1705/7062). Cada `codigo_sidra`,
  por outro lado, corresponde sempre ao mesmo código e nome.
  As mudanças vão de grafia ("(rajado))" → "(rajado)") a escopo ampliado (Refrigerante →
  Refrigerante e água mineral) e produto diferente (Leite pasteurizado → Leite longa vida).
- **Lição:** juntar valores por `(tabela, codigo_sidra)`, nunca só pelo código IBGE; na
  harmonização, código igual não garante categoria igual, e id diferente exige revisão manual.
- **Promovida para:** testes `test_codigo_sidra_identifica_sempre_a_mesma_categoria` e
  `test_mesmo_codigo_ibge_pode_ter_outro_codigo_sidra_entre_pofs`; contrato da
  `dim_classificacao` (id único por tabela); junção do `fato_ipca15` (#5); `METODOLOGIA.md`
  seção 2; ficha; pedido na #6.

### A-011 · 2026-10-19 · Tudo o que o staging consome precisa estar no raw
- **Contexto:** revisão da extração (#3).
- **O que aconteceu:** a primeira versão consultava os metadados e os descartava; a #4 dependeria da
  rede para montar a classificação, e o mesmo raw não garantiria os mesmos marts.
- **Lição:** guardar no raw toda resposta que a transformação usa (valores e metadados), gravar de
  forma atômica e conferir o raw inteiro contra o manifesto.
- **Promovida para:** decisão 0003 (item 2); testes `tests/test_raw_repositorio.py` e
  `test_metadados_vao_para_o_raw_sem_revisao_quando_so_a_periodicidade_avanca`.

### A-010 · 2026-10-19 · Subitem com `nivel = 0` na tabela 1387
- **Contexto:** reconferência das fichas na API (#3), pelo `explorador-sidra`.
- **O que aconteceu:** `4103031.Conjunto infantil` (id 12409) da 1387 vem com `nivel = 0`, o mesmo
  do índice geral e dos grupos nessa tabela; quem contava pelo `nivel` achava 383 subitens, e são 384.
- **Lição:** confirma a A-001 com um caso concreto; a contagem pelo código IBGE é a única confiável.
- **Promovida para:** `PLANEJAMENTO.md` 3.1 (contagens corrigidas); caso de teste pedido na #4.

### A-009 · 2026-10-19 · Variável declarada nos metadados pode vir vazia
- **Contexto:** reconferência das fichas na API (#3).
- **O que aconteceu:** a 1120 (acumulado em 12 meses) consta nos metadados da 1705 e da 7062, mas
  vem `...` em todas as categorias de 2012-02 a 2017-02 (1705) e de 2020-02 a 2020-12 (7062).
- **Lição:** variável listada nos metadados não garante dado. A transformação trata `...` como
  ausente (nunca zero) e o acumulado em 12 meses é calculado e conferido com a 3065.
- **Promovida para:** comentários em `config/series.yaml`; `PLANEJAMENTO.md` 3.1; ficha; validação
  pedida na #5.

### A-008 · 2026-10-19 · Limite de 50 mil valores por requisição no SIDRA
- **Contexto:** reconferência das fichas na API (#3).
- **O que aconteceu:** a API de valores conta variáveis × períodos × categorias (mesmo sem dado) e,
  acima de 50.000, devolve HTTP 400 em texto puro ("Quantidade de valores solicitados: ... excedeu o
  limite: 50000").
- **Lição:** o extrator pede um mês por requisição (cerca de 1.800 valores na 7062); o erro 400 é
  definitivo e não deve ser retentado.
- **Promovida para:** teste `test_erro_400_do_sidra_vira_erro_definitivo_sem_retentativa`; ficha
  `docs/fontes/ibge-sidra.md`.

### A-007 · 2026-10-19 · Troca de POF chega ao IPCA-15 um mês depois do IPCA
- **Contexto:** catálogo de séries (#2), conferindo as versões de POF por tabela.
- **O que aconteceu:** as estruturas novas entram no IPCA em jul/2006, jan/2012 e jan/2020, e no
  IPCA-15 em ago/2006, fev/2012 e fev/2020 (fontes na ficha; fev/2012 confirmado depois pelos metadados da 1705, em #3).
- **Lição:** ao montar o catálogo de outro índice de preços (IPCA cheio, INPC), não copie as datas
  do IPCA-15; confira o início de cada tabela pelos metadados.
- **Promovida para:** teste `test_ipca15_tabelas_e_pofs`; ficha `docs/indices/ipca15.md`;
  conferência automática do catálogo contra os metadados prevista na #3.

### A-006 · 2026-10-19 · Instruções em `AGENTS.md`; `CLAUDE.md` só importa
- **Contexto:** troca de `CLAUDE.md` por `AGENTS.md` (#22).
- **O que aconteceu:** `AGENTS.md` é lido por vários agentes de código, mas o Claude Code carrega
  `CLAUDE.md`. Duas cópias das regras divergiriam.
- **Lição:** as regras ficam só em `AGENTS.md`; cada `CLAUDE.md` contém apenas `@AGENTS.md`. Uma regra
  por pasta exige os dois arquivos na pasta: `AGENTS.md` com o conteúdo e `CLAUDE.md` com o import.
- **Promovida para:** `AGENTS.md` (seção "Aprendizado contínuo"); testes
  `test_todo_claude_md_so_importa_o_agents_md_ao_lado` e `test_todo_agents_md_tem_claude_md_ao_lado`,
  que rodam no CI (#45).

### A-005 · 2026-10-19 · `gh` sem GraphQL nas sessões na nuvem
- **Contexto:** levantamento das issues para a etapa 0 (#20).
- **O que aconteceu:** `gh issue list` e `gh label list` falham com HTTP 403 ("GitHub GraphQL is
  not available from Claude Code sessions").
- **Lição:** nas sessões na nuvem, use a API REST: `gh api repos/{dono}/{repo}/issues`,
  `gh api repos/{dono}/{repo}/labels` etc.
- **Promovida para:** `docs/AGENTES.md` (seção "Ambiente na nuvem").

### A-004 · 2026-10-19 · Rede da sessão na nuvem bloqueia as APIs do IBGE
- **Contexto:** etapa 0 (#20), ao conferir metadados da tabela 7062.
- **O que aconteceu:** `servicodados.ibge.gov.br` e `apisidra.ibge.gov.br` retornam 403 no proxy
  da sessão (política de rede do ambiente).
- **Lição:** antes de extrair dados numa sessão na nuvem, os dois domínios precisam estar em
  *Allowed domains* do ambiente. Sem isso, pare e avise; nunca simule dados. O runner do GitHub
  Actions tem rede própria e é testado na #3.
- **Promovida para:** ficha `docs/fontes/ibge-sidra.md` e `docs/AGENTES.md`.
- **Complemento (#5):** mesmo com as APIs liberadas, `ftp.ibge.gov.br`, `www.ibge.gov.br`,
  `biblioteca.ibge.gov.br` e `agenciadenoticias.ibge.gov.br` seguem bloqueados; para consultar a
  documentação metodológica do IBGE numa sessão, eles também precisam ser liberados.

### A-003 · 2026-10-19 · Planilhas por link quebram o pipeline
- **Contexto:** auditoria do modelo Power BI anterior (`PLANEJAMENTO.md`, 3.3).
- **O que aconteceu:** links de planilhas do Google Drive foram a principal fonte de fragilidade.
- **Lição:** fonte só por API oficial ou CSV versionado em `reference/`.
- **Promovida para:** `CLAUDE.md` (movida para `AGENTS.md` em #22).

### A-002 · 2026-10-19 · IPCA-15 tem classificação própria
- **Contexto:** auditoria do modelo Power BI anterior.
- **O que aconteceu:** o modelo reaproveitava a classificação do IPCA cheio e perdia categorias: em
  7062 há 367 subitens; no IPCA cheio (7060), 377.
- **Lição:** a classificação vem sempre dos metadados da própria tabela.
- **Promovida para:** ficha `docs/indices/ipca15.md`; teste de contagem de categorias previsto na #4.

### A-001 · 2026-10-19 · Campo `nivel` dos metadados não é estável
- **Contexto:** auditoria do modelo Power BI anterior.
- **O que aconteceu:** 7062/1705 começam em 0 = geral; 1646/1387 usam outra escala.
- **Lição:** derive a hierarquia pelo código IBGE no nome da categoria (1 dígito = grupo,
  2 = subgrupo, 4 = item, 7 = subitem).
- **Promovida para:** `CLAUDE.md` (movida para `AGENTS.md` em #22); teste previsto na #4.
