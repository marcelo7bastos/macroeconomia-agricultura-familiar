import pandas as pd
import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.relatorios.revisao import caminho_pagina, coletar, renderizar
from macroaf.transform.harmonizacao import (
    aplicar_decisoes,
    atualizar_mapa,
    conferir_mapa,
    conferir_serie_longa,
    id_ligacao,
    ler_mapa,
    montar_serie_longa,
    parentesco,
    propor_mapa,
)

IPCA15 = carregar_catalogo().indices["ipca15"]
CHAVE = ["tabela_origem", "codigo_sidra_origem", "tabela_destino", "codigo_sidra_destino"]


@pytest.fixture(scope="module")
def base(dados_dim, dados_fato):
    dim = dados_dim
    fato = dados_fato
    return dim, fato, ler_mapa(IPCA15)


@pytest.mark.parametrize(
    ("a", "b", "esperado"),
    [
        ("Livro", "Livro didático", 1.0),
        ("Feijão - carioca (rajado))", "Feijão - carioca (rajado)", 1.0),
        ("Melão", "Telha", 0.0),
        ("Peixe - cavalinha", "Peixe - linguado", 0.0),  # só a palavra genérica em comum
    ],
)
def test_parentesco_de_nomes(a, b, esperado):
    assert parentesco(a, b) == esperado


def test_mapa_do_repositorio_esta_completo_e_coerente(base):
    dim, _, mapa = base
    assert conferir_mapa(mapa, dim, IPCA15) == []


def test_mapa_do_repositorio_esta_em_dia_com_a_proposta(base):
    # Regerar o mapa a partir dos dados não pode mudar o arquivo (revisões são preservadas):
    #   uv run python -m macroaf.transform.harmonizacao
    dim, fato, mapa = base
    regerado = atualizar_mapa(propor_mapa(IPCA15, dim, fato), mapa)
    ordenar = lambda df: df.sort_values(CHAVE).reset_index(drop=True)  # noqa: E731
    pd.testing.assert_frame_equal(ordenar(regerado), ordenar(mapa), check_dtype=False)


def test_mesmo_codigo_com_id_novo_nunca_emenda_sem_revisao(base):
    # A-012 e decisão 0005: id novo é definição nova; nem a grafia igual emenda sem revisão.
    _, _, mapa = base
    mesmo_codigo = mapa[
        (mapa.codigo_ibge_origem == mapa.codigo_ibge_destino)
        & (mapa.codigo_sidra_origem != mapa.codigo_sidra_destino)
    ]
    assert (mesmo_codigo.situacao == "automatico").sum() == 0
    assert len(mesmo_codigo) == 80
    decididas = mesmo_codigo[mesmo_codigo.situacao.isin(["revisado", "rejeitado"])]
    assert decididas.revisor.notna().all()


def test_fusao_com_categoria_que_mantem_o_codigo_aparece(base):
    # A-021: Refrigerante (mesmo código, id novo) + Água mineral (some) -> fusão, não renomeação.
    _, _, mapa = base
    destino = mapa[(mapa.codigo_ibge_destino == "1114083") & (mapa.tabela_origem == 1646)]
    assert set(destino.codigo_ibge_origem) >= {"1114083", "1114096"}
    assert set(destino.tipo_correspondencia) == {"fundido"}


def test_leite_pasteurizado_nao_emenda_no_longa_vida(base):
    dim, fato, mapa = base
    longa = montar_serie_longa(fato, dim, mapa)
    leite = longa[longa.codigo_ibge == "1111004"].groupby("serie_id").nome.unique().map(list)
    assert leite.to_dict() == {
        "1111004@1995-96": ["Leite pasteurizado"],
        "1111004@2008-09": ["Leite longa vida"],
    }
    antiga = longa[longa.serie_id == "1111004@1995-96"].iloc[0]
    # Rejeitada pelo mantenedor na revisão da #6; investigação na issue #32.
    assert antiga.saida == "renomeado (proposta rejeitada)"


def test_revisao_humana_e_preservada_e_emenda_a_serie(base):
    dim, fato, mapa = base
    revisado = mapa.copy()
    linha = (revisado.codigo_ibge_origem == "1111004") & (revisado.tabela_origem == 1387)
    revisado.loc[linha, ["situacao", "revisor"]] = ["revisado", "teste"]
    regerado = atualizar_mapa(propor_mapa(IPCA15, dim, fato), revisado)
    assert (
        regerado[
            (regerado.codigo_ibge_origem == "1111004") & (regerado.tabela_origem == 1387)
        ].situacao
        == "revisado"
    ).all()
    longa = montar_serie_longa(fato, dim, regerado)
    assert longa[longa.codigo_ibge == "1111004"].serie_id.nunique() == 1


def test_revisao_sem_revisor_e_rejeitada(base):
    dim, _, mapa = base
    sem_revisor = mapa.copy()
    sem_revisor.loc[sem_revisor.index[0], "situacao"] = "revisado"
    assert any("sem revisor" in p for p in conferir_mapa(sem_revisor, dim, IPCA15))


def test_serie_longa_respeita_os_invariantes(base):
    dim, fato, mapa = base
    longa = montar_serie_longa(fato, dim, mapa)
    assert conferir_serie_longa(longa, fato) == []
    completas = longa[(longa.inicio_serie == fato.mes.min()) & (longa.fim_serie == fato.mes.max())]
    por_nivel = completas.drop_duplicates("serie_id").nivel_hierarquico.value_counts()
    assert por_nivel["geral"] == 1 and por_nivel["grupo"] == 9
    assert por_nivel["subitem"] >= 200


def _decidir(mapa, filtro, situacao, **outros):
    decidido = mapa.copy()
    decidido.loc[filtro(decidido), ["situacao", "revisor"]] = [situacao, "teste"]
    for coluna, valor in outros.items():
        decidido.loc[filtro(decidido), coluna] = valor
    return decidido


def test_proposta_rejeitada_e_preservada_e_continua_quebra(base):
    dim, fato, mapa = base
    filtro = lambda df: (df.codigo_ibge_origem == "1111004") & (df.tabela_origem == 1387)  # noqa: E731
    regerado = atualizar_mapa(propor_mapa(IPCA15, dim, fato), _decidir(mapa, filtro, "rejeitado"))
    assert (regerado[filtro(regerado)].situacao == "rejeitado").all()
    longa = montar_serie_longa(fato, dim, regerado)
    antiga = longa[longa.serie_id == "1111004@1995-96"].iloc[0]
    assert antiga.saida == "renomeado (proposta rejeitada)"


def test_ligacao_acrescentada_a_mao_substitui_o_descontinuado_automatico(base):
    dim, fato, mapa = base
    # "Massa para pizza" (1646) -> "Massa semipreparada" (1387): fusão que as regras não veem.
    origem = dim[(dim.tabela_sidra == 1646) & (dim.codigo_ibge == "1102038")].iloc[0]
    destino = dim[(dim.tabela_sidra == 1387) & (dim.codigo_ibge == "1102029")].iloc[0]
    manual = mapa.iloc[[0]].copy()
    manual[list(manual.columns)] = None
    manual = manual.assign(
        versao_pof_origem=origem.versao_pof,
        tabela_origem=1646,
        codigo_ibge_origem=origem.codigo_ibge,
        codigo_sidra_origem=origem.codigo_sidra,
        nome_origem=origem.nome,
        versao_pof_destino=destino.versao_pof,
        tabela_destino=1387,
        codigo_ibge_destino=destino.codigo_ibge,
        codigo_sidra_destino=destino.codigo_sidra,
        nome_destino=destino.nome,
        nivel_hierarquico="subitem",
        tipo_correspondencia="fundido",
        situacao="revisado",
        criterio="acrescentada pelo revisor",
        revisor="teste",
    )
    com_manual = pd.concat([mapa, manual], ignore_index=True)
    regerado = atualizar_mapa(propor_mapa(IPCA15, dim, fato), com_manual)
    da_massa = regerado[
        (regerado.tabela_origem == 1646) & (regerado.codigo_ibge_origem == "1102038")
    ]
    assert list(da_massa.tipo_correspondencia) == ["fundido"]
    assert conferir_mapa(regerado, dim, IPCA15) == []


def test_decisao_desatualizada_e_apontada(base):
    dim, _, mapa = base
    filtro = lambda df: (df.codigo_ibge_origem == "1111004") & (df.tabela_origem == 1387)  # noqa: E731
    velho = _decidir(mapa, filtro, "revisado", nome_origem="Nome antigo")
    assert any("desatualizada" in p for p in conferir_mapa(velho, dim, IPCA15))


def test_pagina_de_revisao_esta_em_dia():
    gerada = renderizar(coletar(IPCA15))
    assert caminho_pagina(IPCA15).read_text(encoding="utf-8") == gerada, (
        "regere com: uv run python -m macroaf.relatorios.revisao"
    )


def test_aplicar_decisoes_da_pagina(base):
    _, _, mapa = base
    mapa = mapa.copy()
    candidatas = mapa.index[mapa.situacao == "revisado"][:2]
    mapa.loc[candidatas, ["situacao", "revisor"]] = ["proposto", None]
    aceita, rejeitada = (id_ligacao(r) for r in mapa.loc[candidatas].itertuples())
    decidido = aplicar_decisoes(
        mapa,
        [
            {"id": aceita, "decisao": "aceita"},
            {"id": rejeitada, "decisao": "rejeitada", "observacao": "quebra"},
        ],
        "teste",
    )
    por_id = {id_ligacao(r): r for r in decidido.itertuples()}
    assert por_id[aceita].situacao == "revisado" and por_id[aceita].revisor == "teste"
    assert por_id[rejeitada].situacao == "rejeitado" and por_id[rejeitada].observacao == "quebra"
    with pytest.raises(ValueError, match="não existem"):
        aplicar_decisoes(mapa, [{"id": "L-x-x", "decisao": "aceita"}], "teste")


def test_decisao_do_revisor_tem_o_efeito_certo_na_serie_longa(base):
    # Decisão 0005 como identidade: rejeitada e fundido/dividido nunca emendam;
    # renomeado aceito emenda.
    dim, fato, mapa = base
    longa = montar_serie_longa(fato, dim, mapa)
    serie_de = dict(
        zip(zip(longa.tabela_sidra, longa.codigo_sidra, strict=True), longa.serie_id, strict=True)
    )
    ligadas = mapa.dropna(subset=["codigo_sidra_origem", "codigo_sidra_destino"])
    for r in ligadas[ligadas.situacao.isin(["revisado", "rejeitado"])].itertuples():
        mesma = (
            serie_de[(r.tabela_origem, r.codigo_sidra_origem)]
            == serie_de[(r.tabela_destino, r.codigo_sidra_destino)]
        )
        emenda = r.situacao == "revisado" and r.tipo_correspondencia == "renomeado"
        assert mesma == emenda, id_ligacao(r)


def test_resultado_da_revisao_documentado_bate_com_o_mapa(base):
    # Se o mapa mudar, atualize METODOLOGIA.md 7.4 (116 aceitas, 14 não aceitas, issues #32 a #40).
    _, _, mapa = base
    assert (mapa.situacao == "revisado").sum() == 116
    assert (mapa.situacao == "rejeitado").sum() == 14
    rejeitadas = mapa[mapa.situacao == "rejeitado"]
    assert rejeitadas.observacao.str.contains(r"issue #(?:3[2-9]|40)\)").all()


def test_pagina_de_revisao_mostra_a_observacao_literal():
    # A observação do revisor vai para a página sem processamento de texto (revisão do PR #31).
    html = caminho_pagina(IPCA15).read_text(encoding="utf-8")
    assert ".replace(/: [^:]*$/" not in html
    assert "(investigação: issue #32)" in html
