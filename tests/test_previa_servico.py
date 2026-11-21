"""Etapa 3B — serviço da prévia com banco: o exemplo de CC, idempotência e ausência de escrita."""
from pathlib import Path

from sqlalchemy import event, func, select

from planner.extensions import db
from planner.models import Curso, Disciplina, Encontro, Requisito, Turma
from planner.services.previa_importacao import PreviaImportacaoService

EXEMPLO = Path(__file__).resolve().parent.parent / "examples" / "ciencia-da-computacao"
ARQUIVOS = {n: (EXEMPLO / n).read_bytes() for n in ("curso.csv", "disciplinas.csv", "requisitos.csv", "turmas.csv")}


def _gravar(previa):
    """Stand-in MÍNIMO do commit da 3C, só para testar a idempotência da prévia."""
    r = previa.registros
    c = r["curso.csv"][0]
    curso = Curso(nome=c.nome, versao_matriz=c.versao_matriz)
    db.session.add(curso)
    db.session.flush()
    ids = {}
    for d in r["disciplinas.csv"]:
        disc = Disciplina(curso_id=curso.id, codigo=d.codigo, nome=d.nome, tipo=d.tipo, creditos=d.creditos,
                          carga_h=d.carga_h, periodo_sugerido=d.periodo_sugerido, cor=d.cor,
                          periodicidade=d.periodicidade)
        db.session.add(disc)
        db.session.flush()
        ids[d.codigo] = disc.id
    for q in r["requisitos.csv"]:
        db.session.add(Requisito(disciplina_id=ids[q.disciplina], requisito_id=ids[q.requisito],
                                 tipo=q.tipo, grupo_alt=q.grupo_alt))
    for t in r["turmas.csv"]:
        turma = Turma(disciplina_id=ids[t.disciplina], periodo_letivo=t.periodo_letivo,
                      codigo_turma=t.codigo_turma, docente=t.docente, vagas=t.vagas)
        turma.encontros = [Encontro(dia=e.dia, inicio=e.inicio, fim=e.fim) for e in t.encontros]
        db.session.add(turma)
    db.session.commit()
    return curso


def test_exemplo_de_cc_em_banco_vazio_e_tudo_novo(app):
    p = PreviaImportacaoService().gerar(ARQUIVOS)
    assert p.erros == () and [a.coluna for a in p.avisos] == ["periodicidade"]   # só INF497 (sem turma no quadro)
    assert (p.novos, p.a_atualizar, p.inalterados) == (1 + 49 + 46 + 61, 0, 0)
    assert p.pode_confirmar


def test_previa_nao_grava_nada(app):
    PreviaImportacaoService().gerar(ARQUIVOS)
    assert not db.session.new and not db.session.dirty
    for modelo in (Curso, Disciplina, Requisito, Turma, Encontro):
        assert db.session.scalar(select(func.count()).select_from(modelo)) == 0


def test_importar_o_exemplo_duas_vezes_a_segunda_e_tudo_inalterado(app):
    _gravar(PreviaImportacaoService().gerar(ARQUIVOS))
    p = PreviaImportacaoService().gerar(ARQUIVOS)   # curso achado pelo nome, sem curso_id
    assert p.erros == () and [a.coluna for a in p.avisos] == ["periodicidade"]   # só INF497 (sem turma no quadro)
    assert (p.novos, p.a_atualizar, p.inalterados) == (0, 0, 1 + 49 + 46 + 61)
    assert not p.pode_confirmar                      # nada a gravar
    assert all(a.mantidos_no_banco == 0 for a in p.arquivos)


def test_alteracao_no_csv_aparece_como_atualizar(app):
    curso = _gravar(PreviaImportacaoService().gerar(ARQUIVOS))
    mudado = dict(ARQUIVOS)
    mudado["disciplinas.csv"] = ARQUIVOS["disciplinas.csv"].replace(
        "INF110,Programação I,6,90".encode(), "INF110,Programação I,4,60".encode(), 1)
    p = PreviaImportacaoService().gerar(mudado, curso_id=curso.id)
    item = next(i for i in p.arquivos[1].itens if i.chave == "INF110")
    assert item.acao == "atualizar" and [m.campo for m in item.mudancas] == ["creditos", "carga_h"]
    assert (p.novos, p.a_atualizar) == (0, 1)


def test_estado_carregado_com_consultas_fixas(app):
    curso = _gravar(PreviaImportacaoService().gerar(ARQUIVOS))
    instrucoes = []
    registrar = lambda _c, _cur, instr, *_r: instrucoes.append(instr)
    event.listen(db.engine, "before_cursor_execute", registrar)
    try:
        estado = PreviaImportacaoService().carregar_estado(curso.id)
    finally:
        event.remove(db.engine, "before_cursor_execute", registrar)
    assert (len(estado.disciplinas), len(estado.requisitos), len(estado.turmas)) == (49, 46, 61)
    assert len(instrucoes) <= 6   # curso + disciplinas + requisitos + turmas + encontros: não cresce com os dados


def test_arquivo_desconhecido_vira_erro_na_previa(app):
    p = PreviaImportacaoService().gerar({"notas.csv": b"a,b\n1,2\n"})
    assert [(i.arquivo, i.linha) for i in p.erros] == [("notas.csv", None)]
    assert not p.pode_confirmar


def test_referencia_a_disciplina_do_banco_sem_enviar_disciplinas_csv(app):
    curso = _gravar(PreviaImportacaoService().gerar(ARQUIVOS))
    p = PreviaImportacaoService().gerar(
        {"requisitos.csv": "disciplina,requisito,tipo\nINF112,INF110,pre\nINF112,NAOEXISTE,pre\n"}, curso_id=curso.id)
    assert [(i.linha, i.coluna) for i in p.erros] == [(3, "requisito")]
    assert p.arquivos[0].inalterados == 1
