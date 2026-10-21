# Revisão documental e explicações para gestores

Revisão iniciada em 20/10/2026 e concluída em 21/10/2026, após o PR #58, na issue #59.
O escopo abrangeu os documentos Markdown, os procedimentos de agentes, os dicionários e
os HTMLs gerados. Revisar não significa reescrever registros históricos ou alterar licenças.

| Grupo | Resultado |
|---|---|
| README e planejamento | Situação real dos dois índices, cobertura, componentes implementados e pendências |
| Metodologia | Subgrupos também passam por harmonização; acumulados já implementados; contribuição normalizada pelos pesos; limites da gravação local |
| Fichas de índices | IPCA integrado, referência e raw reais; extensão histórica e revisão humana pendentes; difusão atual calculada, BCB ainda não integrado |
| Ficha do SIDRA | `-` é zero, `...` é ausente; outros sinais não numéricos ainda são erro; referência sem classificação |
| Dicionários | Pontuação da chave composta e “acumulado no ano” corrigidos no gerador e regenerados |
| HTMLs técnicos | Relatórios de IPCA e IPCA-15 regenerados; acesso à nova leitura de gestão |
| Agentes e procedimentos | Dois índices implementados, referências corretas e guias operacionais ligados ao checklist |
| Projeto IPCA | Plano distingue implementado, aceite operacional, 63 propostas pendentes e extensão 1999–2006; URL do plano aponta para main |
| Guias novos | Índice documental, dados, referências, operação, organização e registro do estudo |
| Nova decisão 0008 | Proposta de publicação estática em revisão; alternativas, consequências e autorização da primeira publicação |
| Decisões 0001–0007 | Conteúdo histórico preservado; índice explica evolução da operação e propostas não aceitas |
| Aprendizados A-001–A-035 | Histórico preservado; correções de leitura e ficha da fonte alinhada à A-033 |
| Licenças, CLAUDE.md e modelos não afetados | Conferidos e preservados; sem redefinir termos de uso nem duplicar regras |
| GitHub Pages | Portal estático e fluxo de publicação adicionados; não pressupõe site Quarto implantado |

## Propostas e verificações

A [organização proposta](ESTRUTURA.md) mantém camadas e URLs de consumo. Migrações de módulos,
referências e scripts exigem PR próprio com compatibilidade; nenhuma foi aplicada nesta revisão.

As verificações incluem geração dos documentos, links locais, Ruff, suíte de testes, inspeção
no navegador de abas, teclado, filtros, restauração, exportação e tela pequena. Resultados efetivos
e eventuais pendências de implantação constam no PR; este registro não presume revisão do usuário.
Os CSVs, raw, metadados de dados e decisões de harmonização permanecem preservados.
