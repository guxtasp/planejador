"""Peça 3 (parte A) — simulador de futuro e replanejamento ("e se eu reprovar"). Domínio puro."""
import pytest

from planner.domain.analise import ItemPlano, SemestrePlano
from planner.domain.entidades import Disciplina, Requisito
from planner.domain.simulacao import (R_FORA_DE_OFERTA, R_OFERTA_ESTIMADA, R_PRE_REQUISITO, R_SOBRECARGA,
                                      simular_plano)


def disc(i, creditos=4, per=None, sug=None):
    return Disciplina(i, f"D{i}", f"Disciplina {i}", creditos, "obrigatoria", sug, per)


def sem(periodo, *ids):
    return SemestrePlano(tuple(ItemPlano(i) for i in ids), periodo)


def simular(discs, plano, reqs=(), inicio="2027/1", limite=None, **kw):
    catalogo = {d.id: d for d in discs}
    requisitos = {d.id: [] for d in discs}
    for r in reqs:
        requisitos[r.disciplina_id].append(r)
    return simular_plano(plano, inicio, catalogo, requisitos, {}, limite, **kw)


def tipos(sim):
    return {r.tipo for r in sim.riscos}


def test_disciplina_impar_planejada_em_periodo_par_e_risco_alto_com_proximo_periodo():
    sim = simular([disc(1, per="impar")], [sem("2027/2", 1)])
    risco = next(r for r in sim.riscos if r.tipo == R_FORA_DE_OFERTA)
    assert risco.gravidade == "alta" and risco.detalhe["proximo_periodo"] == "2028/1"


def test_oferta_estimada_pelo_periodo_sugerido_e_marcada_como_estimada_e_nao_alta():
    sim = simular([disc(1, sug=3)], [sem("2027/2", 1)])          # 3º período => ímpar (estimado)
    risco = next(r for r in sim.riscos if r.tipo == R_OFERTA_ESTIMADA)
    assert risco.gravidade == "media"


def test_oferta_desconhecida_nao_vira_sempre_em_silencio():
    sim = simular([disc(1)], [sem("2027/1", 1)])
    assert "oferta_desconhecida" in tipos(sim)


def test_prerequisito_no_mesmo_semestre_e_risco_alto():
    sim = simular([disc(1, per="sempre"), disc(2, per="sempre")], [sem("2027/1", 1, 2)], reqs=[Requisito(2, 1, "pre")])
    assert any(r.tipo == R_PRE_REQUISITO and r.gravidade == "alta" for r in sim.riscos)


def test_o_planejado_antes_conta_como_concluido_depois():
    sim = simular([disc(1, per="sempre"), disc(2, per="sempre")],
                  [sem("2027/1", 1), sem("2027/2", 2)], reqs=[Requisito(2, 1, "pre")])
    assert R_PRE_REQUISITO not in tipos(sim)


def test_sobrecarga_usa_o_limite_do_curso():
    sim = simular([disc(1, 4, "sempre"), disc(2, 4, "sempre")], [sem("2027/1", 1, 2)], limite=6)
    assert R_SOBRECARGA in tipos(sim)


def test_reprovar_em_disciplina_impar_custa_dois_semestres():
    # 1 (ímpar) → 2. Reprovar em 1 em 2027/1: só reabre em 2028/1, e 2 escorrega junto.
    sim = simular([disc(1, per="impar"), disc(2, per="sempre")],
                  [sem("2027/1", 1), sem("2027/2", 2)], reqs=[Requisito(2, 1, "pre")])
    c = next(x for x in sim.cenarios if x.disciplina_id == 1)
    assert c.atraso == 2 and c.espera == 2 and 2 in c.afetadas
    assert sim.resumo.atraso_maximo_reprovacao == 2


def test_periodo_fora_de_ordem_e_detectado():
    sim = simular([disc(1, per="sempre"), disc(2, per="sempre")], [sem("2027/2", 1), sem("2027/1", 2)])
    assert "periodo_fora_de_ordem" in tipos(sim)


def test_disciplina_fora_do_catalogo_e_ignorada_sem_derrubar_a_simulacao():
    sim = simular([disc(1, per="sempre")], [sem("2027/1", 1, 99)])
    assert sim.ignorados == (99,)


def test_periodo_inicial_invalido_levanta_erro():
    with pytest.raises(ValueError):
        simular([disc(1)], [sem(None, 1)], inicio="2027-9")


def test_caminho_critico_conta_o_menor_prazo_com_a_oferta():
    sim = simular([disc(1, per="sempre"), disc(2, per="impar")], [sem("2027/1", 1), sem("2027/2", 2)],
                  reqs=[Requisito(2, 1, "pre")])
    assert sim.critico.menor_semestres == 3 and sim.critico.menor_sem_calendario == 2
