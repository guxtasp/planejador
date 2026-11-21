"""Disciplinas que andam juntas (TCC + Seminário): heurística, validação, otimizador, simulador e replanejamento."""
from planner.domain.analise import ItemPlano, SemestrePlano
from planner.domain.entidades import Disciplina, Requisito
from planner.domain.juntas import (MOTIVO_CORREQUISITO, MOTIVO_NOMES, PROBLEMA_OFERTA, PROBLEMA_PRE,
                                   candidatas_a_juntas, problemas_do_grupo)
from planner.domain.otimizador import ParametrosOtimizacao, otimizar_plano
from planner.domain.preferencias import REGRA_PREFERENCIA, GrupoJunto, PreferenciasAluno
from planner.domain.replanejamento import replanejar
from planner.domain.simulacao import R_GRUPO_IMPOSSIVEL, R_JUNTAS_SEPARADAS, simular_plano

SEMPRE = lambda _d, _t: True


def d(i, nome, per="sempre", sug=None, cr=4, tipo="obrigatoria"):
    return Disciplina(i, f"D{i}", nome, cr, tipo, sug, per)


def cat(*discs):
    return {x.id: x for x in discs}


def reqs(discs, *rs):
    saida = {x.id: [] for x in discs}
    for r in rs:
        saida[r.disciplina_id].append(r)
    return saida


# ── heurística de candidatas ─────────────────────────────────────────────────
def test_tcc_e_seminario_sao_detectados_e_pares_aleatorios_nao():
    discs = [d(1, "Trabalho de Conclusão de Curso", sug=8), d(2, "Seminário de Pesquisa", sug=8),
             d(3, "Cálculo I", sug=1), d(4, "Física I", sug=1), d(5, "Banco de Dados", sug=8)]
    cands = candidatas_a_juntas(discs, reqs(discs))
    assert [(c.disciplinas, c.motivo) for c in cands] == [((1, 2), MOTIVO_NOMES)]


def test_correquisito_mutuo_e_sequenciais_nao():
    discs = [d(1, "Física Teórica"), d(2, "Física Experimental"), d(3, "TCC I", sug=7), d(4, "TCC II", sug=8),
             d(5, "Estágio I", sug=8), d(6, "Estágio II", sug=8)]
    r = reqs(discs, Requisito(1, 2, "co"), Requisito(2, 1, "co"), Requisito(6, 5, "pre"))
    pares = {c.disciplinas: c.motivo for c in candidatas_a_juntas(discs, r)}
    assert pares[(1, 2)] == MOTIVO_CORREQUISITO
    assert (3, 4) not in pares and (5, 6) not in pares       # mesma família / uma exige a outra


# ── grupos impossíveis ───────────────────────────────────────────────────────
def test_grupo_com_ofertas_incompativeis_ou_pre_requisito_e_impossivel():
    discs = [d(1, "A", "impar"), d(2, "B", "par"), d(3, "C"), d(4, "D")]
    r = reqs(discs, Requisito(4, 3, "pre"))
    assert problemas_do_grupo(GrupoJunto((1, 2)), cat(*discs), r)[0].tipo == PROBLEMA_OFERTA
    assert problemas_do_grupo(GrupoJunto((3, 4)), cat(*discs), r)[0].tipo == PROBLEMA_PRE
    assert problemas_do_grupo(GrupoJunto((1, 3)), cat(*discs), r) == ()


# ── otimizador ───────────────────────────────────────────────────────────────
def posicoes(res):
    return {i.disciplina_id: s.posicao for s in res.semestres for i in s.itens}


def test_otimizador_respeita_o_grupo_como_bloco():
    # 1 → 2 (pré); 3 é livre. Sem grupo, 3 vai para o 1º semestre; com "2 junto com 3", os dois ficam juntos.
    discs = [d(1, "A"), d(2, "B"), d(3, "C")]
    r = reqs(discs, Requisito(2, 1, "pre"))
    com = otimizar_plano(cat(*discs), r, {}, set(), "2027/1",
                         ParametrosOtimizacao(max_creditos=8, preferencias=PreferenciasAluno(juntas=(GrupoJunto((2, 3)),))))
    p = posicoes(com)
    assert p[2] == p[3] and p[1] < p[2] and com.grupos_aplicados == ((2, 3),)


def test_grupo_com_ofertas_incompativeis_e_ignorado_sem_bloquear_o_resto():
    discs = [d(1, "A", "impar"), d(2, "B", "par")]
    res = otimizar_plano(cat(*discs), reqs(discs), {}, set(), "2027/1",
                         ParametrosOtimizacao(preferencias=PreferenciasAluno(juntas=(GrupoJunto((1, 2)),))))
    assert res.viavel and res.grupos_aplicados == () and set(posicoes(res)) == {1, 2}


def test_preferencia_tenta_juntar_sem_obrigar():
    discs = [d(1, "A"), d(2, "B"), d(3, "C")]
    g = GrupoJunto((2, 3), REGRA_PREFERENCIA)
    res = otimizar_plano(cat(*discs), reqs(discs, Requisito(2, 1, "pre")), {}, set(), "2027/1",
                         ParametrosOtimizacao(max_creditos=8, preferencias=PreferenciasAluno(juntas=(g,))))
    p = posicoes(res)
    assert p[2] == p[3] and res.grupos_aplicados == ()


# ── simulador ────────────────────────────────────────────────────────────────
def simular(discs, plano, r=None, juntas=()):
    return simular_plano(plano, plano[0].periodo_letivo, cat(*discs), r or reqs(discs), {}, None,
                         preferencias=PreferenciasAluno(juntas=juntas), n_monte_carlo=0)


def sem(periodo, *ids):
    return SemestrePlano(tuple(ItemPlano(i) for i in ids), periodo)


def test_simulador_avisa_quando_o_grupo_esta_separado_e_diz_para_onde_mover():
    discs = [d(1, "TCC"), d(2, "Seminário")]
    sim = simular(discs, [sem("2027/1", 1), sem("2027/2", 2)], juntas=(GrupoJunto((1, 2)),))
    r = next(x for x in sim.riscos if x.tipo == R_JUNTAS_SEPARADAS)
    assert r.gravidade == "media" and r.detalhe["destino"] == 2
    from planner.services.simulacao_json import mensagem_risco
    msg, acao = mensagem_risco(r, cat(*discs))
    assert "semestres diferentes" in msg and "semestre 2" in acao
    junto = simular(discs, [sem("2027/1", 1, 2)], juntas=(GrupoJunto((1, 2)),))
    assert R_JUNTAS_SEPARADAS not in {x.tipo for x in junto.riscos}
    assert junto.semestres[0].itens[0].junto_com == (2,)


def test_simulador_explica_grupo_impossivel():
    discs = [d(1, "A", "impar"), d(2, "B", "par")]
    sim = simular(discs, [sem("2027/1", 1), sem("2027/2", 2)], juntas=(GrupoJunto((1, 2)),))
    assert R_GRUPO_IMPOSSIVEL in {x.tipo for x in sim.riscos}


# ── replanejamento: obrigatória × preferência ────────────────────────────────
def test_reprovar_em_uma_adia_o_grupo_obrigatorio_junto():
    discs = [d(1, "TCC"), d(2, "Seminário")]
    r = reqs(discs)
    obrig = replanejar([{1, 2}], SEMPRE, r, {}, None, reprovar={1}, juntas=[{1, 2}])
    assert obrig.concluida_em == {1: 1, 2: 1}                      # o Seminário espera o TCC
    livre = replanejar([{1, 2}], SEMPRE, r, {}, None, reprovar={1})   # preferência: nada é arrastado
    assert livre.concluida_em == {1: 1, 2: 0}


def test_grupo_obrigatorio_so_entra_completo_no_semestre():
    discs = [d(1, "TCC"), d(2, "Seminário"), d(3, "Base")]
    r = reqs(discs, Requisito(2, 3, "pre"))
    res = replanejar([{1, 2, 3}], SEMPRE, r, {}, None, juntas=[{1, 2}])
    assert res.concluida_em == {3: 0, 1: 1, 2: 1}                 # 2 só pode depois de 3; 1 espera por 2


# ── fim de curso (TCC & cia.) e os dois TCCs ─────────────────────────────────
from planner.domain.fim_de_curso import disciplinas_de_fim_de_curso


def test_dois_tccs_com_elaboracao_e_seminario_viram_pares_no_mesmo_periodo():
    discs = [d(1, "TCC I", sug=7), d(2, "Elaboração de TCC", sug=7), d(3, "TCC II", sug=8), d(4, "Seminários", sug=8),
             d(5, "Banco de Dados", sug=7)]
    r = reqs(discs, Requisito(3, 1, "pre"))
    pares = {c.disciplinas for c in candidatas_a_juntas(discs, r)}
    assert (1, 2) in pares and (3, 4) in pares and (1, 3) not in pares
    assert disciplinas_de_fim_de_curso(cat(*discs), r) == {1: 1, 2: 1, 3: 0, 4: 0}


def test_seminario_do_meio_do_curso_nao_e_fim_de_curso():
    discs = [d(1, "Projeto Final", sug=8), d(2, "Seminário de Pesquisa", sug=3)]
    assert disciplinas_de_fim_de_curso(cat(*discs), reqs(discs)) == {1: 0}


def test_sugestao_poe_o_tcc_no_fim_mesmo_sem_requisito():
    # TCC só exige A; sem a regra ele cairia no 2º semestre. Com ela, fica no último.
    discs = [d(1, "A", sug=1), d(2, "B", sug=2), d(3, "C", sug=3), d(4, "D", sug=4), d(5, "Trabalho de Conclusão", sug=4)]
    res = otimizar_plano(cat(*discs), reqs(discs, Requisito(2, 1), Requisito(3, 2), Requisito(4, 3), Requisito(5, 1)),
                         {}, set(), "2027/1", ParametrosOtimizacao(max_creditos=8))
    p = posicoes(res)
    assert p[5] == max(p.values())


def test_simulador_avisa_tcc_cedo_demais():
    from planner.domain.simulacao import R_FIM_CEDO
    discs = [d(1, "A"), d(2, "B"), d(3, "TCC")]
    sim = simular(discs, [sem("2027/1", 3), sem("2027/2", 1), sem("2028/1", 2)])
    r = next(x for x in sim.riscos if x.tipo == R_FIM_CEDO)
    assert r.detalhe["destino"] == 3
