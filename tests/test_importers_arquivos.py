"""Etapa 3A — cada importador: campos, enums, tamanhos, 'vazio = desconhecido'."""
from datetime import time
from decimal import Decimal

import pytest

from planner.domain.entidades import Encontro
from planner.importers import (
    CursoImporter, DisciplinaImporter, RequisitoImporter, TurmaImporter, Severidade,
)


def erros_de(resultado):
    return [(i.linha, i.coluna) for i in resultado.erros]


# ───────────────────────── curso.csv ─────────────────────────
class TestCurso:
    def test_so_nome_e_obrigatorio_e_o_resto_fica_vazio(self):
        r = CursoImporter().importar("nome\nCiência da Computação\n")
        c = r.registros[0]
        assert c.nome == "Ciência da Computação"
        assert (c.instituicao, c.creditos_obrigatorios, c.max_creditos_semestre, c.dias_letivos) == (None,) * 4

    def test_campos_completos(self):
        r = CursoImporter().importar(
            "nome,instituicao,versao_matriz,creditos_obrigatorios,creditos_optativos_exigidos,ch_total,"
            "max_creditos_semestre,duracao_semestres,dias_letivos\n"
            "Curso X,Univ Y,2024,150,20,3000,28,8,SEG|TER|QUA|QUI|SEX|SAB\n")
        c = r.registros[0]
        assert not r.issues
        assert (c.creditos_obrigatorios, c.max_creditos_semestre, c.duracao_semestres) == (150, 28, 8)
        assert c.dias_letivos == ("SEG", "TER", "QUA", "QUI", "SEX", "SAB")

    def test_nome_em_branco_e_numero_invalido(self):
        r = CursoImporter().importar("nome,max_creditos_semestre,duracao_semestres\n,abc,0\n")
        assert not r.registros
        assert {c for _, c in erros_de(r)} == {"nome", "max_creditos_semestre", "duracao_semestres"}

    def test_dia_letivo_invalido(self):
        r = CursoImporter().importar("nome,dias_letivos\nX,SEG|XYZ\n")
        assert erros_de(r) == [(2, "dias_letivos")]

    def test_mais_de_uma_linha_e_ambiguo(self):
        r = CursoImporter().importar("nome\nCurso A\nCurso B\n")
        assert [c.nome for c in r.registros] == ["Curso A"]
        assert erros_de(r) == [(3, None)]


# ───────────────────────── disciplinas.csv ─────────────────────────
class TestDisciplinas:
    CAB = "codigo,nome,tipo,creditos,carga_h,periodo_sugerido,cor\n"

    def importar(self, linhas):
        return DisciplinaImporter().importar(self.CAB + linhas)

    def test_linha_completa(self):
        r = self.importar("INF110,Programação I,obrigatoria,6,90,1,#3B82F6\n")
        d = r.registros[0]
        assert not r.issues
        assert (d.codigo, d.tipo, d.creditos, d.carga_h, d.periodo_sugerido, d.cor) == \
               ("INF110", "obrigatoria", 6, 90, 1, "#3b82f6")

    def test_vazio_e_desconhecido_nunca_zero(self):
        d = self.importar("OPT1,Tópicos,optativa,,,,\n").registros[0]
        assert (d.creditos, d.carga_h, d.periodo_sugerido, d.cor) == (None, None, None, None)

    def test_zero_explicito_e_diferente_de_vazio(self):
        d = self.importar("INF497,Projeto Final,obrigatoria,0,0,7,\n").registros[0]
        assert (d.creditos, d.carga_h) == (0, 0)

    def test_tipo_em_branco_nao_e_assumido(self):
        r = self.importar("INF110,Programação I,,6,90,1,\n")
        assert not r.registros and erros_de(r) == [(2, "tipo")]

    @pytest.mark.parametrize("bruto, esperado", [
        ("Obrigatória", "obrigatoria"), ("OPTATIVA", "optativa"), ("Eletivo", "eletiva"),
    ])
    def test_tipo_aceita_caixa_acento_e_genero(self, bruto, esperado):
        assert self.importar(f"X1,Nome,{bruto},,,,\n").registros[0].tipo == esperado

    def test_tipo_invalido_lista_as_opcoes(self):
        r = self.importar("X1,Nome,especial,,,,\n")
        assert "obrigatoria" in r.erros[0].mensagem and "optativa" in r.erros[0].mensagem

    @pytest.mark.parametrize("creditos", ["-1", "4,5", "abc", "4h"])
    def test_creditos_invalidos(self, creditos):
        assert erros_de(self.importar(f'X1,Nome,obrigatoria,"{creditos}",,,\n')) == [(2, "creditos")]

    def test_numeros_no_estilo_excel_sao_aceitos(self):
        d = self.importar("X1,Nome,obrigatoria,6.0,90,1,\n").registros[0]
        assert d.creditos == 6

    def test_periodo_sugerido_minimo_1(self):
        assert erros_de(self.importar("X1,Nome,obrigatoria,4,60,0,\n")) == [(2, "periodo_sugerido")]

    @pytest.mark.parametrize("cor", ["azul", "#12345", "3b82f6", "#GGGGGG"])
    def test_cor_invalida(self, cor):
        assert erros_de(self.importar(f"X1,Nome,obrigatoria,4,60,1,{cor}\n")) == [(2, "cor")]

    def test_tamanhos_maximos_do_banco(self):
        r = self.importar(f"{'C' * 31},{'N' * 201},obrigatoria,,,,\n")
        assert {c for _, c in erros_de(r)} == {"codigo", "nome"}

    def test_espacos_internos_do_codigo_sao_colapsados_e_caixa_preservada(self):
        assert self.importar("MAT  140a,Cálculo,obrigatoria,,,,\n").registros[0].codigo == "MAT 140a"

    def test_multiplos_erros_na_mesma_linha_sao_todos_reportados(self):
        r = self.importar("X1,Nome,xx,abc,-1,0,rosa\n")
        assert {c for _, c in erros_de(r)} == {"tipo", "creditos", "carga_h", "periodo_sugerido", "cor"}


# ───────────────────────── requisitos.csv ─────────────────────────
class TestRequisitos:
    def importar(self, linhas, cab="disciplina,requisito,tipo,grupo_alt\n"):
        return RequisitoImporter().importar(cab + linhas)

    def test_and_e_or(self):
        r = self.importar("INF213,INF112,pre,\nEST200,MAT140,pre,A\nEST200,MAT141,pre,A\n")
        assert not r.issues
        assert [(x.disciplina, x.requisito, x.tipo, x.grupo_alt) for x in r.registros] == [
            ("INF213", "INF112", "pre", None), ("EST200", "MAT140", "pre", "A"), ("EST200", "MAT141", "pre", "A")]

    @pytest.mark.parametrize("bruto, esperado", [
        ("pré-requisito", "pre"), ("Pre", "pre"), ("CO", "co"), ("Correquisito", "co"), ("co-requisito", "co"),
    ])
    def test_sinonimos_de_tipo(self, bruto, esperado):
        assert self.importar(f"A,B,{bruto},\n").registros[0].tipo == esperado

    def test_tipo_invalido_ou_vazio(self):
        r = self.importar("A,B,talvez,\nA,C,,\n")
        assert erros_de(r) == [(2, "tipo"), (3, "tipo")]

    def test_autorrequisito_e_erro(self):
        r = self.importar("INF110,inf110,pre,\n")
        assert erros_de(r) == [(2, "requisito")] and "si mesma" in r.erros[0].mensagem

    def test_codigo_em_branco(self):
        assert erros_de(self.importar(",B,pre,\nA,,pre,\n")) == [(2, "disciplina"), (3, "requisito")]

    def test_coluna_grupo_e_opcional_e_alias(self):
        assert self.importar("A,B,pre\n", cab="disciplina,requisito,tipo\n").registros[0].grupo_alt is None
        assert self.importar("A,B,pre,X\n", cab="codigo,requisito,tipo,grupo\n").registros[0].grupo_alt == "X"


# ───────────────────────── turmas.csv ─────────────────────────
class TestTurmas:
    CAB = "disciplina,periodo_letivo,codigo_turma,docente,vagas,horarios,local\n"

    def importar(self, linhas):
        return TurmaImporter().importar(self.CAB + linhas)

    def test_turma_com_varios_encontros(self):
        r = self.importar('INF110,2026/1,T1,Ana,40,"SEG 16:00-18:00 | QUI 14:00-16:00 | SEX 14:00-16:00"\n')
        t = r.registros[0]
        assert not r.issues
        assert (t.disciplina, t.periodo_letivo, t.codigo_turma, t.docente, t.vagas) == \
               ("INF110", "2026/1", "T1", "Ana", 40)
        assert t.encontros[0] == Encontro("SEG", time(16), time(18)) and len(t.encontros) == 3

    def test_turmas_alternativas_sao_linhas_distintas(self):
        r = self.importar("INF110,2026/1,T1,,,SEG 08:00-10:00\nINF110,2026/1,T2,,,TER 08:00-10:00\n")
        assert [t.codigo_turma for t in r.registros] == ["T1", "T2"]
        assert [len(t.encontros) for t in r.registros] == [1, 1]

    def test_horario_ausente_e_aviso_e_a_turma_e_mantida(self):
        r = self.importar("INF497,2026/1,T1,,,\n")
        assert len(r.registros) == 1 and r.registros[0].encontros == ()
        assert [i.severidade for i in r.issues] == [Severidade.AVISO]

    def test_horario_invalido_descarta_a_turma_inteira(self):
        r = self.importar('INF110,2026/1,T1,,,"SEG 08:00-10:00 | QUA 12:00-11:00"\n')
        assert not r.registros and erros_de(r) == [(2, "horarios")]

    @pytest.mark.parametrize("periodo, esperado", [("2026/1", "2026/1"), ("2026.2", "2026/2"), ("2026-01", "2026/1")])
    def test_periodo_letivo_normalizado(self, periodo, esperado):
        assert self.importar(f"X1,{periodo},T1,,,\n").registros[0].periodo_letivo == esperado

    @pytest.mark.parametrize("periodo", ["26/1", "2026", "2026/0", "2026/x", "primeiro"])
    def test_periodo_letivo_invalido(self, periodo):
        assert erros_de(self.importar(f"X1,{periodo},T1,,,\n")) == [(2, "periodo_letivo")]

    def test_periodo_letivo_e_codigo_turma_sao_obrigatorios(self):
        r = self.importar("X1,,,,,\n")
        assert {c for _, c in erros_de(r)} == {"periodo_letivo", "codigo_turma"}

    def test_vagas_invalidas(self):
        assert erros_de(self.importar("X1,2026/1,T1,,muitas,\n")) == [(2, "vagas")]

    def test_local_e_opcional_e_aceita_o_alias_sala(self):
        assert self.importar("A,2026/1,T1,,,SEG 08:00-10:00,\n").registros[0].local is None
        r = TurmaImporter().importar("disciplina,periodo_letivo,codigo_turma,horarios,sala\n"
                                     "A,2026/1,T1,SEG 08:00-10:00,PVA 201\n")
        assert r.registros[0].local == "PVA 201" and not r.issues

    def test_aliases_de_colunas(self):
        r = TurmaImporter().importar(
            "codigo,periodo,turma,professor,horario\nX1,2026/1,P1,Bia,SAB 08:00-12:00\n")
        t = r.registros[0]
        assert (t.codigo_turma, t.docente, t.encontros[0].dia) == ("P1", "Bia", "SAB") and not r.erros
