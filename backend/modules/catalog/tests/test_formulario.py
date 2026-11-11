"""Campos da automação: validação dos campos, conversão dos valores (forma brasileira),
padrão, obrigatório e a ponte com o JSON Schema do manifesto."""

from __future__ import annotations

import dataclasses

import pytest

from modules.catalog.domain import formulario as f
from modules.catalog.domain.formulario import Campo, FormularioInvalido, converter, validar_campos, valores


def c(tipo: str, **kw) -> Campo:
    return Campo(kw.pop("chave", "x"), kw.pop("rotulo", "X"), tipo, **kw)


# -- conversão ---------------------------------------------------------------------------------

@pytest.mark.parametrize("tipo,entrada,saida", [
    ("texto", "  Folha  ", "Folha"), ("texto", 10, "10"), ("pasta", r" F:\saida ", r"F:\saida"),
    ("email", " folha@biason.net ", "folha@biason.net"),
    ("inteiro", "42", 42), ("inteiro", 7, 7), ("inteiro", " 3 ", 3),
    ("numero", "1,5", 1.5), ("numero", "1.234,56", 1234.56), ("numero", "2.5", 2.5), ("numero", 3, 3),
    ("numero", 2.25, 2.25), ("numero", "1 000,5", 1000.5),
    ("sim_nao", True, True), ("sim_nao", False, False), ("sim_nao", "Sim", True), ("sim_nao", "não", False),
    ("sim_nao", "1", True), ("sim_nao", "0", False), ("sim_nao", "nao", False), ("sim_nao", " S ", True),
    ("data", "31/10/2026", "2026-10-31"), ("data", "2026-10-31", "2026-10-31"),
    ("mes_ano", "10/2026", "10/2026"), ("mes_ano", "1/2026", "01/2026"), ("mes_ano", "102026", "10/2026"),
    ("mes_ano", "2026-10", "10/2026"), ("mes_ano", " 12/2026 ", "12/2026"),
    ("json", {"a": [1, 2]}, {"a": [1, 2]}),
])
def test_converte_para_o_tipo(tipo, entrada, saida) -> None:
    campo = c(tipo, opcoes=("a",)) if tipo == "lista" else c(tipo)
    assert converter(campo, entrada) == saida


@pytest.mark.parametrize("tipo,entrada,trecho", [
    ("texto", "a" * 2001, "até 2000"), ("pasta", "a" * 2001, "até 2000"),
    ("email", "folha", "e-mail inválido"), ("email", "a@b", "e-mail inválido"), ("email", "a b@c.d", "e-mail inválido"),
    ("inteiro", "4,5", "inteiro"), ("inteiro", True, "inteiro"), ("inteiro", "x", "inteiro"),
    ("numero", "abc", "número"), ("numero", True, "número"),
    ("sim_nao", "talvez", "sim ou não"),
    ("data", "31/02/2026", "data inválida"), ("data", "ontem", "data inválida"),
    ("mes_ano", "13/2026", "MM/AAAA"), ("mes_ano", "00/2026", "MM/AAAA"), ("mes_ano", "10-2026", "MM/AAAA"),
    ("mes_ano", "10/1899", "MM/AAAA"), ("mes_ano", "10/3000", "MM/AAAA"), ("mes_ano", "2026-13", "MM/AAAA"),
])
def test_valor_invalido(tipo, entrada, trecho) -> None:
    with pytest.raises(ValueError, match=trecho):
        converter(c(tipo), entrada)


def test_texto_longo_no_limite() -> None:
    assert converter(c("texto_longo"), "a" * 20000) == "a" * 20000
    assert converter(c("texto"), "a" * 2000) == "a" * 2000
    with pytest.raises(ValueError, match="até 20000"):
        converter(c("texto_longo"), "a" * 20001)


def test_limites_exatos_de_mes_e_ano() -> None:
    assert converter(c("mes_ano"), "01/1900") == "01/1900" and converter(c("mes_ano"), "12/2999") == "12/2999"


def test_lista_so_aceita_as_opcoes() -> None:
    campo = c("lista", opcoes=("completo", "rubricas"))
    assert converter(campo, " rubricas ") == "rubricas"
    with pytest.raises(ValueError, match="escolha uma das opções: completo, rubricas"):
        converter(campo, "tudo")


def test_tipo_desconhecido() -> None:
    with pytest.raises(ValueError, match="tipo desconhecido: xpto"):
        converter(c("xpto"), "a")


# -- campos ------------------------------------------------------------------------------------

def test_campos_validos_com_padrao_convertido_e_opcoes_sem_repeticao() -> None:
    campos = validar_campos([
        {"chave": "competencia", "rotulo": " Competência ", "tipo": "mes_ano", "obrigatorio": True, "ajuda": " MM/AAAA "},
        {"chave": "modo", "rotulo": "Modo", "tipo": "lista", "opcoes": ["completo", "rubricas", "completo", " "],
         "padrao": "completo"},
        {"chave": "limite", "rotulo": "Limite", "tipo": "numero", "padrao": "2,5", "afeta_trabalho": True},
        {"chave": "obs", "rotulo": "Obs"},
    ])
    assert campos[0] == Campo("competencia", "Competência", "mes_ano", True, None, (), "MM/AAAA", False)
    assert campos[1].opcoes == ("completo", "rubricas") and campos[1].padrao == "completo"
    assert (campos[2].padrao, campos[2].afeta_trabalho) == (2.5, True)
    assert (campos[3].tipo, campos[3].obrigatorio, campos[3].ajuda) == ("texto", False, None)


def test_publico() -> None:
    assert Campo("m", "Modo", "lista", True, "a", ("a", "b"), "ajuda", True, "automacao", True).publico() == {
        "chave": "m", "rotulo": "Modo", "tipo": "lista", "obrigatorio": True, "padrao": "a", "opcoes": ["a", "b"],
        "ajuda": "ajuda", "afeta_trabalho": True, "origem": "automacao", "fora_de_uso": True}


@pytest.mark.parametrize("brutos,erro", [
    ("x", "campos"),
    ([{"chave": "x", "rotulo": "X"}] * 61, "campos"),
    (["texto"], "campos[0]"),
    ([{"chave": "Competencia", "rotulo": "C"}], "campos[0].chave"),
    ([{"chave": "1a", "rotulo": "C"}], "campos[0].chave"),
    ([{"chave": "a" * 61, "rotulo": "C"}], "campos[0].chave"),
    ([{"chave": "a", "rotulo": " "}], "campos[0].rotulo"),
    ([{"chave": "a", "rotulo": "x" * 121}], "campos[0].rotulo"),
    ([{"chave": "a", "rotulo": "A", "tipo": "cpf"}], "campos[0].tipo"),
    ([{"chave": "a", "rotulo": "A", "tipo": "lista"}], "campos[0].opcoes"),
    ([{"chave": "a", "rotulo": "A", "tipo": "lista", "opcoes": "x"}], "campos[0].opcoes"),
    ([{"chave": "a", "rotulo": "A", "tipo": "lista", "opcoes": [str(i) for i in range(101)]}], "campos[0].opcoes"),
    ([{"chave": "a", "rotulo": "A", "tipo": "inteiro", "padrao": "x"}], "campos[0].padrao"),
    ([{"chave": "a", "rotulo": "A"}, {"chave": "a", "rotulo": "B"}], "campos[1].chave"),
])
def test_campos_invalidos(brutos, erro) -> None:
    with pytest.raises(FormularioInvalido) as exc:
        validar_campos(brutos)
    assert erro in exc.value.campos


def test_limites_exatos_dos_campos() -> None:
    assert len(validar_campos([{"chave": f"c{i}", "rotulo": "C"} for i in range(60)])) == 60
    assert validar_campos([{"chave": "a" * 60, "rotulo": "x" * 120}])[0].chave == "a" * 60
    opcoes = [str(i) for i in range(100)]
    assert len(validar_campos([{"chave": "a", "rotulo": "A", "tipo": "lista", "opcoes": opcoes}])[0].opcoes) == 100
    assert validar_campos([{"chave": "a", "rotulo": "A", "tipo": "lista", "opcoes": ["só"]}])[0].opcoes == ("só",)
    assert validar_campos([{"chave": "a", "rotulo": "A", "ajuda": "x" * 400}])[0].ajuda == "x" * 300


def test_todos_os_erros_de_uma_vez() -> None:
    with pytest.raises(FormularioInvalido) as exc:
        validar_campos([{"chave": "A", "rotulo": ""}, {"chave": "b", "rotulo": "B", "tipo": "lista"}])
    assert set(exc.value.campos) == {"campos[0].chave", "campos[0].rotulo", "campos[1].opcoes"}
    assert "campos[0].chave" in str(exc.value)


# -- valores -----------------------------------------------------------------------------------

ENTRADA = [Campo("competencia", "Competência", "mes_ano", True),
           Campo("modo", "Modo", "lista", True, "completo", ("completo", "rubricas")),
           Campo("enviar_email", "Avisar", "sim_nao", False, True),
           Campo("obs", "Obs")]


def test_valores_aplica_padrao_converte_e_omite_vazio_opcional() -> None:
    assert valores(ENTRADA, {"competencia": "102026", "obs": "  "}) == {
        "competencia": "10/2026", "modo": "completo", "enviar_email": True}
    assert valores(ENTRADA, {"competencia": "10/2026", "enviar_email": "não", "modo": "rubricas"}) == {
        "competencia": "10/2026", "modo": "rubricas", "enviar_email": False}


def test_falso_explicito_nao_vira_padrao() -> None:
    assert valores([Campo("a", "A", "sim_nao", False, True)], {"a": False}) == {"a": False}
    assert valores([Campo("n", "N", "inteiro", False, 5)], {"n": 0}) == {"n": 0}


def test_valores_obrigatorio_tipo_e_desconhecido() -> None:
    with pytest.raises(FormularioInvalido) as exc:
        valores(ENTRADA, {"modo": "tudo", "xpto": 1})
    assert exc.value.campos == {"xpto": "campo desconhecido nesta automação", "competencia": "obrigatório",
                                "modo": "escolha uma das opções: completo, rubricas"}


def test_valores_sem_nada_e_formato_errado() -> None:
    assert valores([Campo("a", "A")], None) == {}
    with pytest.raises(FormularioInvalido, match="envie um objeto"):
        valores([Campo("a", "A")], ["a"])


def test_colunas_de_item_mantem_o_que_nao_e_campo() -> None:
    colunas = [Campo("pasta", "Pasta", "pasta", True), Campo("separa", "Separa", "sim_nao", False, False)]
    assert valores(colunas, {"pasta": "F:\\x", "rubricas_ignoradas": [{"codigo": 450}]}, manter_extras=True) == {
        "rubricas_ignoradas": [{"codigo": 450}], "pasta": "F:\\x", "separa": False}


# -- JSON Schema -------------------------------------------------------------------------------

def test_de_esquema_json() -> None:
    esquema = {"type": "object", "required": ["codigo"], "properties": {
        "codigo": {"type": "string", "title": "Código"},
        "separar_por_custo": {"type": "boolean", "title": "Separar por custo", "default": False},
        "centros": {"type": "integer"}, "valor": {"type": "number"},
        "inicio": {"type": "string", "format": "date"}, "email": {"type": "string", "format": "email"},
        "modo": {"type": "string", "enum": ["a", "b"], "description": "qual"},
        "rubricas_ignoradas": {"type": "array"}, "Invalida": {"type": "string"}, "ruim": "x"}}
    campos = {x.chave: x for x in f.de_esquema_json(esquema, ["separar_por_custo"])}
    assert list(campos) == ["codigo", "separar_por_custo", "centros", "valor", "inicio", "email", "modo", "rubricas_ignoradas"]
    assert (campos["codigo"].rotulo, campos["codigo"].tipo, campos["codigo"].obrigatorio) == ("Código", "texto", True)
    assert (campos["separar_por_custo"].tipo, campos["separar_por_custo"].padrao, campos["separar_por_custo"].afeta_trabalho) == (
        "sim_nao", False, True)
    assert [campos[k].tipo for k in ("centros", "valor", "inicio", "email", "modo", "rubricas_ignoradas")] == [
        "inteiro", "numero", "data", "email", "lista", "json"]
    assert (campos["modo"].opcoes, campos["modo"].ajuda, campos["centros"].rotulo) == (("a", "b"), "qual", "centros")
    assert campos["centros"].afeta_trabalho is False and campos["centros"].obrigatorio is False
    assert f.de_esquema_json(None) == [] and f.de_esquema_json({"properties": "x"}) == []


def test_para_esquema_json() -> None:
    esquema = f.para_esquema_json([
        Campo("pasta", "Pasta", "pasta", True), Campo("n", "N", "numero"), Campo("i", "I", "inteiro"),
        Campo("s", "S", "sim_nao"), Campo("m", "M", "lista", opcoes=("a", "b")), Campo("j", "J", "json")])
    assert esquema == {"type": "object", "required": ["pasta"], "properties": {
        "pasta": {"type": "string", "title": "Pasta"}, "n": {"type": "number", "title": "N"},
        "i": {"type": "integer", "title": "I"}, "s": {"type": "boolean", "title": "S"},
        "m": {"type": "string", "enum": ["a", "b"], "title": "M"}, "j": {"title": "J"}}}
    assert "required" not in f.para_esquema_json([Campo("a", "A")])


def test_de_guardados_e_formulario() -> None:
    assert f.de_guardados(None) == [] and f.de_guardados([{"chave": "a", "rotulo": "A"}])[0].chave == "a"
    vazio = f.Formulario()
    assert (vazio.entrada, vazio.colunas, vazio.origem) == ([], [], "manifesto")


def test_campo_imutavel_e_constantes() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        Campo("a", "A").rotulo = "B"  # type: ignore[misc]
    assert f.TIPOS == ("texto", "texto_longo", "numero", "inteiro", "sim_nao", "data", "mes_ano", "lista", "email",
                       "pasta", "json")
    assert (f.LIMITE_CAMPOS, f.LIMITE_OPCOES, f.LIMITE_TEXTO, f.LIMITE_TEXTO_LONGO) == (60, 100, 2000, 20000)


# -- reforços vindos do teste de mutação ---------------------------------------------------------

def _de_fora(texto: str) -> str:
    """O mesmo texto, mas outro objeto (como quando vem do banco ou da rede)."""
    return "".join(list(texto))


@pytest.mark.parametrize("tipo,entrada,saida", [
    ("texto", " a ", "a"), ("pasta", " p ", "p"), ("email", "a@b.cd", "a@b.cd"), ("inteiro", "4", 4),
    ("numero", "1,5", 1.5), ("sim_nao", "sim", True), ("data", "31/10/2026", "2026-10-31"),
    ("mes_ano", "102026", "10/2026"), ("json", [1], [1]),
])
def test_tipo_que_vem_de_fora_converte_igual(tipo, entrada, saida) -> None:
    assert converter(Campo("x", "X", _de_fora(tipo)), entrada) == saida


def test_lista_e_texto_longo_vindos_de_fora() -> None:
    assert converter(Campo("x", "X", _de_fora("lista"), opcoes=("a",)), "a") == "a"
    assert converter(Campo("x", "X", _de_fora("texto_longo")), "a" * 2500) == "a" * 2500
    assert f.para_esquema_json([Campo("m", "M", _de_fora("lista"), opcoes=("a",))])["properties"]["m"]["enum"] == ["a"]


@pytest.mark.parametrize("tipo", ["abc", "cpf", "zz"])
def test_tipo_desconhecido_em_qualquer_ordem_alfabetica(tipo) -> None:
    with pytest.raises(ValueError, match=f"tipo desconhecido: {tipo}"):
        converter(c(tipo), "31/10/2026")


def test_esquema_com_tipo_json_vindo_de_fora_e_tipo_estranho() -> None:
    esquema = {"properties": {
        "b": {"type": _de_fora("boolean")}, "i": {"type": _de_fora("integer")}, "n": {"type": _de_fora("number")},
        "s": {"type": _de_fora("string")}, "z": {"type": "zzz"}}}
    assert [x.tipo for x in f.de_esquema_json(esquema)] == ["sim_nao", "inteiro", "numero", "texto", "json"]


def test_propriedade_invalida_no_meio_nao_para_a_leitura() -> None:
    esquema = {"properties": {"a": {"type": "string"}, "Ruim": {"type": "string"}, "x": "nao e objeto",
                              "b": {"type": "boolean"}}}
    assert [x.chave for x in f.de_esquema_json(esquema)] == ["a", "b"]


def test_opcional_vazio_antes_do_obrigatorio() -> None:
    campos = [Campo("obs", "Obs"), Campo("competencia", "C", "mes_ano", True)]
    with pytest.raises(FormularioInvalido) as exc:
        valores(campos, {})
    assert exc.value.campos == {"competencia": "obrigatório"}
    assert valores(campos, {"competencia": "1/2026"}) == {"competencia": "01/2026"}


def test_campo_invalido_no_meio_nao_esconde_os_seguintes() -> None:
    with pytest.raises(FormularioInvalido) as exc:
        validar_campos([{"chave": "a", "rotulo": "A"}, {"chave": "B", "rotulo": "B"}, {"chave": "c", "rotulo": ""}])
    assert set(exc.value.campos) == {"campos[1].chave", "campos[2].rotulo"}


@pytest.mark.parametrize("bruto,esperado", [
    ({"chave": "X", "rotulo": "X", "tipo": "inteiro", "padrao": "abc"}, {"campos[0].chave"}),
    ({"chave": "x", "rotulo": "", "tipo": "inteiro", "padrao": "abc"}, {"campos[0].rotulo"}),
    ({"chave": "x", "rotulo": "X", "tipo": "lista", "padrao": "zz"}, {"campos[0].opcoes"}),
])
def test_campo_ja_invalido_nao_confere_o_padrao(bruto, esperado) -> None:
    with pytest.raises(FormularioInvalido) as exc:
        validar_campos([bruto])
    assert set(exc.value.campos) == esperado


def test_padroes_do_campo_e_chamada_por_nome() -> None:
    campo = Campo("a", "A")
    assert (campo.tipo, campo.obrigatorio, campo.padrao, campo.opcoes, campo.ajuda, campo.afeta_trabalho) == (
        "texto", False, None, (), None, False)
    assert valores(campos=[campo], recebidos={"a": "x"}) == {"a": "x"}


def test_lista_vinda_de_um_json_de_verdade() -> None:
    import json

    brutos = json.loads('[{"chave": "modo", "rotulo": "Modo", "tipo": "lista", "opcoes": ["a", "b"], "padrao": "b"}]')
    assert validar_campos(brutos)[0].opcoes == ("a", "b")
    sem_opcoes = [{"chave": "modo", "rotulo": "Modo", "tipo": _de_fora("lista")}]
    with pytest.raises(FormularioInvalido) as exc:
        validar_campos(sem_opcoes)
    assert "campos[0].opcoes" in exc.value.campos


def test_obrigatorio_vazio_nao_esconde_o_erro_dos_seguintes() -> None:
    campos = [Campo("competencia", "C", "mes_ano", True), Campo("email", "E", "email")]
    with pytest.raises(FormularioInvalido) as exc:
        valores(campos, {"email": "nao-e-email"})
    assert exc.value.campos == {"competencia": "obrigatório", "email": "e-mail inválido"}


def test_chave_repetida_nao_esconde_os_erros_seguintes() -> None:
    with pytest.raises(FormularioInvalido) as exc:
        validar_campos([{"chave": "a", "rotulo": "A"}, {"chave": "a", "rotulo": "B"}, {"chave": "c", "rotulo": ""}])
    assert set(exc.value.campos) == {"campos[1].chave", "campos[2].rotulo"}



# -- origem e junção (Fase 8) --------------------------------------------------------------------

def test_origem_e_fora_de_uso_lidos_e_guardados() -> None:
    campos = validar_campos([{"chave": "a", "rotulo": "A", "origem": "automacao", "fora_de_uso": True},
                             {"chave": "b", "rotulo": "B", "origem": "qualquer"}, {"chave": "c", "rotulo": "C"}])
    assert [(c.origem, c.fora_de_uso) for c in campos] == [("automacao", True), ("portal", False), ("portal", False)]
    assert validar_campos([{"chave": "p", "rotulo": "P", "tipo": "inteiro", "padrao": "3", "origem": "automacao"}])[0] ==         Campo("p", "P", "inteiro", False, 3, (), None, False, "automacao", False)
    assert (f.ORIGEM_AUTOMACAO, f.ORIGEM_PORTAL) == ("automacao", "portal")
    assert [c.origem for c in f.de_esquema_json({"properties": {"a": {"type": "string"}}})] == ["automacao"]


def test_fora_de_uso_nao_e_exigido_mas_e_conferido() -> None:
    campo = Campo("velho", "Velho", "inteiro", True, fora_de_uso=True)
    assert valores([campo], {}) == {}
    with pytest.raises(FormularioInvalido):
        valores([campo], {"velho": "x"})


def test_da_automacao() -> None:
    assert f.da_automacao([Campo("a", "A", fora_de_uso=True)]) == [Campo("a", "A", origem="automacao")]


def test_juntar_so_acrescenta_e_marca_o_que_saiu() -> None:
    atuais = [
        Campo("competencia", "Competência (editado)", "mes_ano", True, origem="automacao"),
        Campo("velho", "Velho", origem="automacao"),
        Campo("responsavel", "Responsável", "email", origem="portal"),
        Campo("voltou", "Voltou", origem="automacao", fora_de_uso=True),
        Campo("ja_saiu", "Já saiu", origem="automacao", fora_de_uso=True),
    ]
    declarados = [Campo("competencia", "Competência", "mes_ano", True), Campo("modo", "Modo", "lista", opcoes=("a",)),
                  Campo("voltou", "Voltou")]
    campos, mudou = f.juntar(atuais, declarados)
    assert [(c.chave, c.rotulo, c.origem, c.fora_de_uso) for c in campos] == [
        ("competencia", "Competência (editado)", "automacao", False),  # o que o Portal editou vale
        ("velho", "Velho", "automacao", True),                         # saiu da automação: fica, marcado
        ("responsavel", "Responsável", "portal", False),               # criado no Portal: nunca tocado
        ("voltou", "Voltou", "automacao", False),
        ("ja_saiu", "Já saiu", "automacao", True),
        ("modo", "Modo", "automacao", False),                          # novo: entra no fim
    ]
    assert mudou == {"novos": ["modo"], "fora_de_uso": ["velho"], "voltaram": ["voltou"]}


def test_juntar_sem_mudanca() -> None:
    atuais = [Campo("a", "A", origem="automacao")]
    campos, mudou = f.juntar(atuais, [Campo("a", "Outro nome")])
    assert campos == atuais and mudou == {"novos": [], "fora_de_uso": [], "voltaram": []}
    assert f.juntar([], []) == ([], {"novos": [], "fora_de_uso": [], "voltaram": []})


def test_juntar_campo_do_portal_com_a_mesma_chave_da_automacao() -> None:
    campos, mudou = f.juntar([Campo("a", "A", origem="portal")], [Campo("a", "A")])
    assert campos == [Campo("a", "A", origem="portal")] and mudou["novos"] == []


def test_edicao_no_portal_mantem_as_marcas_gravadas() -> None:
    atuais = [Campo("competencia", "Competência", "mes_ano", origem="automacao"),
              Campo("modo", "Modo", "texto", origem="automacao", fora_de_uso=True)]
    # O navegador manda tudo como "portal" (ou forja "automacao" num campo novo): não vale.
    editados = [Campo("competencia", "Mês", "mes_ano"), Campo("modo", "Modo", "texto", fora_de_uso=False),
                Campo("obs", "Obs", "texto", origem="automacao", fora_de_uso=True)]
    saida = f.manter_marcas(atuais, editados)
    assert [(x.chave, x.rotulo, x.origem, x.fora_de_uso) for x in saida] == [
        ("competencia", "Mês", "automacao", False), ("modo", "Modo", "automacao", True), ("obs", "Obs", "portal", False)]
    assert f.manter_marcas([], []) == []


def test_origem_vinda_de_fora_vale_pelo_texto() -> None:
    automacao = "".join(["auto", "macao"])  # montado em tempo de execução, como vem do JSON
    (lido,) = validar_campos([{"chave": "x", "rotulo": "X", "tipo": "texto", "origem": automacao}])
    assert lido.origem == "automacao"
    campo = Campo("x", "X", "texto", origem=automacao)
    saida, mudou = f.juntar([campo], [])
    assert mudou["fora_de_uso"] == ["x"] and saida[0].fora_de_uso is True
