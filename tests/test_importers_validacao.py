"""
Etapa 3B — validação referencial/semântica e prévia (dry-run), SEM banco.

Os CSVs são escritos em texto, passam pelos importadores da 3A e só então
pela validação, exatamente como no uso real.
"""
from datetime import time

import pytest

from planner.domain.entidades import Encontro
from planner.importers import IMPORTADORES
from planner.importers.base import Severidade
from planner.importers.validacao import (CursoExistente, DisciplinaExistente, EstadoExistente,
                                         RequisitoExistente, TurmaExistente, gerar_previa)

CAB = {
    "curso.csv": "nome,duracao_semestres\n",
    "disciplinas.csv": "codigo,nome,tipo,creditos,carga_h,periodo_sugerido\n",
    "requisitos.csv": "disciplina,requisito,tipo,grupo_alt\n",
    "turmas.csv": "disciplina,periodo_letivo,codigo_turma,docente,vagas,horarios,local\n",
}
BASE = "A1,Alfa,obrigatoria,4,60,1\nB1,Beta,obrigatoria,4,60,2\nC1,Gama,obrigatoria,4,60,3\n"


def previa(estado=None, **corpos):
    """`previa(disciplinas=..., requisitos=...)`: usa o cabeçalho padrão de cada arquivo."""
    leituras = {}
    for nome, corpo in corpos.items():
        arquivo = f"{nome}.csv"
        leituras[arquivo] = IMPORTADORES[arquivo].importar(CAB[arquivo] + corpo)
    return gerar_previa(leituras, estado)


def problemas(p, severidade=None):
    """[(arquivo, linha, coluna)] dos problemas, opcionalmente só de uma severidade."""
    return [(i.arquivo, i.linha, i.coluna) for i in p.issues if severidade in (None, i.severidade)]


def erros(p):
    return problemas(p, Severidade.ERRO)


def avisos(p):
    """Avisos das regras testadas aqui; o de periodicidade tem testes próprios (test_periodicidade_validacao)."""
    return [a for a in problemas(p, Severidade.AVISO) if a[2] != "periodicidade"]


def arquivo(p, nome):
    return next(a for a in p.arquivos if a.arquivo == nome)


ESTADO = EstadoExistente(
    curso=CursoExistente("Curso X", duracao_semestres=8),
    disciplinas=(
        DisciplinaExistente("A1", "Alfa", "obrigatoria", 4, 60, 1),
        DisciplinaExistente("B1", "Beta", "obrigatoria", 4, 60, 2),
    ),
    requisitos=(RequisitoExistente("B1", "A1", "pre"),),
    turmas=(TurmaExistente("A1", "2026/1", "T1", "Ana", 30, (Encontro("SEG", time(8), time(10)),)),),
)


class TestDuplicatas:
    def test_codigo_repetido_com_valores_diferentes_e_erro_e_mantem_a_primeira(self):
        p = previa(disciplinas=BASE + "A1,Outro nome,obrigatoria,4,60,1\n")
        assert erros(p) == [("disciplinas.csv", 5, "codigo")]
        assert "linha 2" in p.erros[0].mensagem
        assert [i.chave for i in arquivo(p, "disciplinas.csv").itens] == ["A1", "B1", "C1"]
        assert arquivo(p, "disciplinas.csv").descartadas == 1

    def test_linha_identica_e_so_aviso_e_e_ignorada(self):
        p = previa(disciplinas=BASE + "a1,alfa,OBRIGATORIA,4,60,1\n")
        assert erros(p) == [] and avisos(p) == [("disciplinas.csv", 5, "codigo")]
        assert len(arquivo(p, "disciplinas.csv").itens) == 3

    def test_duplicata_ignora_caixa_e_acento_no_codigo(self):
        p = previa(disciplinas=BASE + "á1,Outro,obrigatoria,,,\n")  # 'á1' != 'A1'? normaliza sem acento
        assert erros(p) == [("disciplinas.csv", 5, "codigo")]

    def test_requisito_e_turma_repetidos(self):
        p = previa(
            disciplinas=BASE,
            requisitos="B1,A1,pre,\nB1,A1,pre,\nC1,B1,pre,\nC1,B1,pre,G1\n",
            turmas="A1,2026/1,T1,Ana,,SEG 08:00-10:00\nA1,2026.1,T1,Bia,,SEG 08:00-10:00\n",
        )
        assert problemas(p) == [
            ("requisitos.csv", 3, None), ("requisitos.csv", 5, None), ("turmas.csv", 3, None)]
        assert avisos(p) == [("requisitos.csv", 3, None)]          # idêntico → aviso
        assert len(erros(p)) == 2                                    # valores diferentes → erro



class TestReferencial:
    def test_requisito_para_disciplina_inexistente(self):
        p = previa(disciplinas=BASE, requisitos="B1,ZZZ,pre,\nYYY,A1,pre,\n")
        assert erros(p) == [("requisitos.csv", 2, "requisito"), ("requisitos.csv", 3, "disciplina")]
        assert arquivo(p, "requisitos.csv").itens == ()

    def test_turma_para_disciplina_inexistente(self):
        p = previa(disciplinas=BASE, turmas="ZZZ,2026/1,T1,,,SEG 08:00-10:00,\n")
        assert erros(p) == [("turmas.csv", 2, "disciplina")]

    def test_referencia_resolve_contra_o_banco(self):
        # Só requisitos.csv enviado: A1 e B1 existem no banco.
        p = previa(ESTADO, requisitos="B1,A1,pre,\n")
        assert erros(p) == []

    def test_disciplina_so_no_arquivo_serve_de_referencia(self):
        p = previa(ESTADO, disciplinas="Z9,Nova,optativa,,,\n", requisitos="Z9,A1,pre,\n")
        assert erros(p) == []

    def test_codigos_sao_comparados_sem_caixa_e_saem_canonicos(self):
        p = previa(disciplinas=BASE, requisitos="b1,a1,pre,\n", turmas="a1,2026/1,t1,,,\n")
        assert erros(p) == []
        req = p.registros["requisitos.csv"][0]
        assert (req.disciplina, req.requisito) == ("B1", "A1")
        assert p.registros["turmas.csv"][0].disciplina == "A1"

    def test_caixa_diferente_do_banco_vira_a_mesma_disciplina_com_aviso(self):
        p = previa(ESTADO, disciplinas="a1,Alfa,obrigatoria,4,60,1\n")
        assert avisos(p) == [("disciplinas.csv", 2, "codigo")]
        assert p.registros["disciplinas.csv"][0].codigo == "A1"
        assert arquivo(p, "disciplinas.csv").novos == 0            # não cria 'a1' ao lado de 'A1'

    def test_erro_de_schema_na_disciplina_explica_a_referencia_quebrada(self):
        p = previa(disciplinas="A1,Alfa,\nB1,Beta,obrigatoria,,,\n", requisitos="B1,A1,pre,\n")
        assert "descartada" in [i for i in p.erros if i.arquivo == "requisitos.csv"][0].mensagem


class TestSemantica:
    def test_ciclo_de_prerequisito_e_erro_e_descarta_as_linhas_do_ciclo(self):
        p = previa(disciplinas=BASE, requisitos="A1,B1,pre,\nB1,C1,pre,\nC1,A1,pre,\n")
        assert erros(p) == [("requisitos.csv", n, "requisito") for n in (2, 3, 4)]
        assert arquivo(p, "requisitos.csv").itens == ()
        assert "A1, B1, C1" in p.erros[0].mensagem

    def test_ciclo_fecha_com_requisito_ja_gravado(self):
        # Banco: B1 exige A1. Arquivo: A1 exige B1 → ciclo; só a linha do arquivo é descartada.
        p = previa(ESTADO, requisitos="A1,B1,pre,\n")
        assert erros(p) == [("requisitos.csv", 2, "requisito")]

    def test_correquisito_mutuo_nao_e_ciclo(self):
        p = previa(disciplinas=BASE, requisitos="A1,B1,co,\nB1,A1,co,\n")
        assert erros(p) == []

    def test_ciclo_atraves_de_grupo_ou_so_avisa(self):
        # B1 exige (A1 ou C1); A1 exige B1. C1 é saída → não é impossível.
        p = previa(disciplinas=BASE, requisitos="B1,A1,pre,G\nB1,C1,pre,G\nA1,B1,pre,\n")
        assert erros(p) == []
        assert ("requisitos.csv", 2, "requisito") in avisos(p)
        assert len(arquivo(p, "requisitos.csv").itens) == 3

    def test_requisito_em_periodo_posterior_ou_igual(self):
        p = previa(disciplinas=BASE, requisitos="A1,C1,pre,\nB1,B1x,pre,\n")
        # A1 (período 1) exige C1 (período 3): aviso. (Linha 3 é erro referencial e não entra.)
        assert ("requisitos.csv", 2, "requisito") in avisos(p)
        p2 = previa(disciplinas="A1,Alfa,obrigatoria,,,2\nB1,Beta,obrigatoria,,,2\n", requisitos="B1,A1,pre,\nB1,A1,co,\n")
        assert avisos(p2) == [("requisitos.csv", 2, "requisito")]   # pre no mesmo período; co no mesmo período é ok

    def test_periodo_desconhecido_nao_gera_aviso(self):
        p = previa(disciplinas="A1,Alfa,obrigatoria,,,\nB1,Beta,obrigatoria,,,1\n", requisitos="A1,B1,pre,\n")
        assert avisos(p) == []

    def test_grupo_ou_com_um_unico_membro(self):
        p = previa(disciplinas=BASE, requisitos="C1,A1,pre,G1\nC1,B1,pre,\n")
        assert avisos(p) == [("requisitos.csv", 2, "grupo_alt")]

    def test_grupo_ou_completo_com_o_banco_nao_avisa(self):
        estado = EstadoExistente(
            disciplinas=ESTADO.disciplinas, requisitos=(RequisitoExistente("B1", "A1", "pre", "G"),))
        p = previa(estado, requisitos="B1,C1,pre,G\n", disciplinas="C1,Gama,obrigatoria,,,3\n")
        assert [a for a in avisos(p) if a[2] == "grupo_alt"] == []

    def test_encontros_sobrepostos_na_mesma_turma_descartam_a_turma(self):
        p = previa(disciplinas=BASE, turmas=(
            "A1,2026/1,T1,,,SEG 08:00-10:00 | SEG 09:00-11:00\n"
            "A1,2026/1,T2,,,SEG 08:00-10:00 | SEG 10:00-12:00\n"))   # encostar não é sobrepor
        assert erros(p) == [("turmas.csv", 2, "horarios")]
        assert [i.chave for i in arquivo(p, "turmas.csv").itens] == ["A1 · 2026/1 · T2"]

    @pytest.mark.parametrize("cred, ch, avisa", [(4, 60, False), (6, 90, False), (4, 15, True),
                                                  (2, 90, True), (0, 30, True), (0, 0, False)])
    def test_razao_creditos_carga_horaria(self, cred, ch, avisa):
        p = previa(disciplinas=f"A1,Alfa,obrigatoria,{cred},{ch},1\n")
        assert (avisos(p) == [("disciplinas.csv", 2, "carga_h")]) is avisa

    def test_razao_so_com_os_dois_valores_conhecidos(self):
        assert avisos(previa(disciplinas="A1,Alfa,obrigatoria,4,,1\nB1,Beta,obrigatoria,,60,1\n")) == []

    def test_periodo_acima_da_duracao_do_curso(self):
        p = previa(curso="Curso X,4\n", disciplinas="A1,Alfa,obrigatoria,,,5\n")
        assert avisos(p) == [("disciplinas.csv", 2, "periodo_sugerido")]
        # sem duração conhecida (nem no arquivo, nem no banco): nada a julgar
        assert avisos(previa(disciplinas="A1,Alfa,obrigatoria,,,50\n")) == []

    def test_mudanca_de_tipo_avisa(self):
        p = previa(ESTADO, disciplinas="A1,Alfa,optativa,4,60,1\n")
        assert avisos(p) == [("disciplinas.csv", 2, "tipo")]



class TestPrevia:
    def test_tudo_novo_em_curso_vazio(self):
        p = previa(curso="Curso X,8\n", disciplinas=BASE, requisitos="B1,A1,pre,\n")
        assert (p.novos, p.a_atualizar, p.inalterados) == (5, 0, 0)
        assert p.pode_confirmar

    def test_novo_atualizar_inalterado_e_mantido(self):
        p = previa(ESTADO, disciplinas=(
            "A1,Alfa,obrigatoria,4,60,1\n"       # igual → inalterado
            "B1,Beta Novo,obrigatoria,6,90,2\n"   # muda nome, créditos e CH
            "C1,Gama,obrigatoria,4,60,3\n"))      # nova
        itens = {i.chave: i for i in arquivo(p, "disciplinas.csv").itens}
        assert [itens[c].acao for c in ("A1", "B1", "C1")] == ["inalterado", "atualizar", "novo"]
        assert [(m.campo, m.antes, m.depois) for m in itens["B1"].mudancas] == [
            ("nome", "Beta", "Beta Novo"), ("creditos", 4, 6), ("carga_h", 60, 90)]
        assert (p.novos, p.a_atualizar, p.inalterados) == (1, 1, 1)

    def test_celula_vazia_nao_apaga_valor_conhecido(self):
        p = previa(ESTADO, disciplinas="A1,Alfa,obrigatoria,,,\n")
        assert arquivo(p, "disciplinas.csv").itens[0].acao == "inalterado"

    def test_o_que_esta_so_no_banco_e_mantido_e_contado(self):
        p = previa(ESTADO, disciplinas="A1,Alfa,obrigatoria,4,60,1\n")
        assert arquivo(p, "disciplinas.csv").mantidos_no_banco == 1   # B1

    def test_requisito_so_muda_o_grupo(self):
        p = previa(ESTADO, requisitos="B1,A1,pre,\n")
        assert arquivo(p, "requisitos.csv").itens[0].acao == "inalterado"
        p2 = previa(ESTADO, requisitos="B1,A1,pre,G\n")
        item = arquivo(p2, "requisitos.csv").itens[0]
        assert item.acao == "atualizar"          # (o aviso de grupo único é outro assunto)
        assert [(m.campo, m.antes, m.depois) for m in item.mudancas] == [("grupo_alt", None, "G")]

    def test_turma_compara_encontros_sem_depender_da_ordem(self):
        existente = TurmaExistente("A1", "2026/1", "T1", None, None, (
            Encontro("SEG", time(8), time(10)), Encontro("QUA", time(8), time(10))))
        estado = EstadoExistente(disciplinas=ESTADO.disciplinas, turmas=(existente,))
        igual = previa(estado, turmas="A1,2026/1,T1,,,QUA 08:00-10:00 | SEG 08:00-10:00\n")
        assert arquivo(igual, "turmas.csv").itens[0].acao == "inalterado"
        muda = previa(estado, turmas="A1,2026/1,T1,,,SEG 08:00-10:00 | QUA 10:00-12:00\n")
        m = arquivo(muda, "turmas.csv").itens[0].mudancas[0]
        assert (m.campo, m.antes, m.depois) == (
            "encontros", "QUA 08:00-10:00 | SEG 08:00-10:00", "QUA 10:00-12:00 | SEG 08:00-10:00")

    def test_turma_de_outro_periodo_e_nova(self):
        p = previa(ESTADO, turmas="A1,2026/2,T1,,,SEG 08:00-10:00\n")
        assert arquivo(p, "turmas.csv").itens[0].acao == "novo"

    def test_curso_existente_com_nome_diferente_aparece_como_renomeacao(self):
        p = previa(ESTADO, curso="Curso Y,8\n")
        item = arquivo(p, "curso.csv").itens[0]
        assert item.acao == "atualizar" and item.mudancas[0].campo == "nome"

    def test_erro_impede_confirmar_e_arquivo_vazio_tambem(self):
        assert not previa(disciplinas=BASE, requisitos="B1,ZZZ,pre,\n").pode_confirmar
        assert not previa(ESTADO, disciplinas="A1,Alfa,obrigatoria,4,60,1\n").pode_confirmar  # nada a gravar

    def test_aviso_nao_impede_confirmar(self):
        p = previa(disciplinas="A1,Alfa,obrigatoria,4,15,1\n")
        assert avisos(p) and p.pode_confirmar

    def test_contadores_por_arquivo_e_json(self):
        p = previa(disciplinas=BASE + "X,Sem tipo,,,,\n", requisitos="B1,A1,pre,\n")
        a = arquivo(p, "disciplinas.csv")
        assert (a.linhas_lidas, len(a.itens), a.descartadas, a.erros) == (4, 3, 1, 1)
        d = p.para_dict()
        assert d["totais"]["erros"] == 1 and d["pode_confirmar"] is False
        assert d["arquivos"][0]["arquivo"] == "disciplinas.csv"
        import json
        json.dumps(d)  # tudo serializável

    def test_arquivos_nao_enviados_nao_aparecem(self):
        assert [a.arquivo for a in previa(disciplinas=BASE).arquivos] == ["disciplinas.csv"]

    def test_previa_e_deterministica_e_nao_altera_as_leituras(self):
        leituras = {
            "disciplinas.csv": IMPORTADORES["disciplinas.csv"].importar(CAB["disciplinas.csv"] + BASE + "A1,X,optativa,,,\n"),
            "requisitos.csv": IMPORTADORES["requisitos.csv"].importar(CAB["requisitos.csv"] + "b1,a1,pre,\nB1,ZZ,pre,\n"),
        }
        antes = {k: (list(v.registros), list(v.issues)) for k, v in leituras.items()}
        primeira = gerar_previa(leituras, ESTADO)
        segunda = gerar_previa(dict(reversed(list(leituras.items()))), ESTADO)   # ordem do dict não importa
        assert primeira.para_dict() == segunda.para_dict()
        assert {k: (list(v.registros), list(v.issues)) for k, v in leituras.items()} == antes

    def test_problemas_ordenados_por_arquivo_e_linha(self):
        p = previa(disciplinas=BASE + "A1,X,optativa,,,\n", requisitos="B1,ZZ,pre,\n")
        ordem = [(i.arquivo, i.linha) for i in p.issues]
        assert ordem == sorted(ordem, key=lambda t: (["disciplinas.csv", "requisitos.csv"].index(t[0]), t[1]))

    def test_problemas_da_3a_aparecem_na_previa(self):
        p = previa(disciplinas="A1,Alfa,\n")
        assert erros(p) == [("disciplinas.csv", 2, "tipo")]
