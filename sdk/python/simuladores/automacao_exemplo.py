"""Automação de exemplo, no formato da Integração Contábil: o mesmo código roda no modo
agente e no modo direto. O modo vem só das variáveis de ambiente.

    python -m automacao_exemplo
"""

from __future__ import annotations

import sys

from portal_automacoes import Automacao

EMPRESAS = [
    {"codigo": "5081", "nome": "Strassburger", "matriz": "5081", "separa": False, "centros": []},
    {"codigo": "5066", "nome": "Planet Shoes", "matriz": "5066", "separa": True, "centros": [33, 35, 37]},
]


def tela(texto: str, tom: int):
    """Imagem de tela sintética (os testes não têm a Domínio)."""
    from PIL import Image, ImageDraw

    imagem = Image.new("RGB", (640, 360), (230, 236, 242))
    desenho = ImageDraw.Draw(imagem)
    desenho.rectangle((0, 0, 640, 40), fill=(20, 40, 69))
    desenho.rectangle((40, 80, 600, 320), outline=(tom, 90, 140), width=3)
    desenho.text((50, 12), "Domínio Folha (simulada)", fill=(255, 255, 255))
    desenho.text((60, 100), texto, fill=(20, 30, 55))
    return imagem


def main() -> int:
    with Automacao.conectar(versao_automacao="exemplo-1.0") as a:
        with a.etapa("iniciar"):
            a.log("Abrindo a Domínio")
            a.passo("Domínio carregada", tipo="abriu", imagem=tela("Tela inicial", 40))
            with a.pausa("reinicio", "sessão aberta há 60 min"):
                a.log("Reiniciando a Domínio", nivel="aviso")
        for empresa in EMPRESAS:
            with a.item(empresa["codigo"], rotulo=empresa["nome"], grupo=empresa["matriz"],
                        configuracao={"separar_por_custo": empresa["separa"]}):
                with a.etapa("trocar_empresa"):
                    a.passo(f"Empresa ativa confirmada: {empresa['nome']}", tipo="acao", imagem=tela(empresa["nome"], 90))
                alvos = empresa["centros"] or [None]
                with a.etapa("rubricas", tarefas_previstas=len(alvos)) as etapa:
                    for i, centro in enumerate(alvos, 1):
                        a.progresso(i, len(alvos), f"centro {centro}" if centro else "empresa inteira")
                        a.log("Ainda gerando (15s)...", espera=True)
                        a.passo("Gerar acionado", tipo="acao", imagem=tela(f"Gerar {centro or ''}", 140))
                        etapa.tarefa_concluida()
                if empresa["separa"]:
                    a.atencao("Rubricas a parametrizar", colunas=[("codigo", "Rubrica"), ("descricao", "Descrição")],
                              linhas=[{"codigo": 8781, "descricao": "AJUDA DE CUSTO"}],
                              acoes=[{"id": "ignorar", "rotulo": "Ignorar", "tipo": "adicionar_a_lista",
                                      "lista": "rubricas_ignoradas", "coluna": "codigo", "no_grupo": True}])
                    a.resumo("1 rubrica a parametrizar")
                else:
                    with a.etapa("txt", tarefas_previstas=1) as etapa:
                        a.log("Gravado: Strassburger 102026.TXT (login com senha=NaoDeveAparecer)")
                        etapa.tarefa_concluida()
                    a.resumo("1 TXT gerado")
            if a.deve_parar():
                a.log("Parada pedida pelo Portal: empresas restantes canceladas", nivel="aviso")
                break
    print(f"modo={a.modo} pendentes={a.pendentes} recusados={a.recusados}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
