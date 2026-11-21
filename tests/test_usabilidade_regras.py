"""
Regras que nasceram da avaliação de uso: rotina × curso numa resposta só, quadro publicado manda
na sugestão, riscos repetidos agrupados, cartão "pelo seu plano" sempre com a melhor data conhecida.
"""
from datetime import time

from planner.domain.entidades import Disciplina, Encontro, Turma
from planner.domain.otimizador import ParametrosOtimizacao, otimizar_plano
from planner.domain.preferencias import PreferenciasAluno
from planner.domain.semana import BlocoIndisponivel, PreferenciasSemana, rotina_comporta
from planner.services.simulacao_json import grupos_de_riscos, rotina_json


def enc(dia, h1, h2):
    return Encontro(dia, time(h1), time(h2))


MANHA = PreferenciasSemana(tuple(BlocoIndisponivel(d, time(8), time(12), "trabalho")
                                 for d in ("SEG", "TER", "QUA", "QUI", "SEX")))


# ── rotina × curso ───────────────────────────────────────────────────────────
def test_rotina_classifica_por_todas_as_turmas_conhecidas():
    turmas = {
        1: [Turma(10, 1, (enc("SEG", 8, 10),), "2026/1")],                                   # só de manhã
        2: [Turma(20, 2, (enc("TER", 8, 10),), "2026/1"), Turma(21, 2, (enc("TER", 19, 21),), "2026/1")],
        3: [Turma(30, 3, (), "2026/1")],                                                     # sem horário
    }
    r = rotina_comporta([1, 2, 3, 4], turmas, MANHA)
    assert (r.cabem, r.nao_cabem, r.sem_turma) == ((2,), (1,), (3, 4))
    # sem horários bloqueados, tudo que tem turma cabe
    assert rotina_comporta([1, 2], turmas, None).nao_cabem == ()


def test_rotina_json_responde_em_uma_frase():
    discs = {1: Disciplina(1, "MAT140", "Cálculo", 4), 2: Disciplina(2, "INF100", "Intro", 4)}
    r = rotina_json(rotina_comporta([1, 2], {1: [Turma(10, 1, (enc("SEG", 8, 10),))],
                                             2: [Turma(20, 2, (enc("SEG", 14, 16),))]}, MANHA), discs, True)
    assert r["nivel"] == "alto" and r["titulo"] == "Com a sua rotina, 1 obrigatória não cabe"
    assert "MAT140" in r["texto"] and r["acao"]
    ok = rotina_json(rotina_comporta([2], {2: [Turma(20, 2, (enc("SEG", 14, 16),))]}, MANHA), discs, True)
    assert ok["nivel"] == "ok" and ok["titulo"] == "Sua rotina comporta o curso"
    assert rotina_json(rotina_comporta([2], {}, None), discs, False) is None


def test_riscos_repetidos_viram_grupo():
    class R:
        def __init__(self, tipo, gravidade="media"):
            self.tipo, self.gravidade = tipo, gravidade
    grupos = grupos_de_riscos([R("horario_indisponivel")] * 4 + [R("sobrecarga")] + [R("horario_projetado", "baixa")] * 5)
    assert grupos == [{"tipo": "horario_indisponivel", "n": 4,
                       "titulo": "4 disciplinas caem em horários que você bloqueou"}]


# ── quadro publicado manda na sugestão ───────────────────────────────────────
def test_sugestao_nao_poe_disciplina_em_periodo_cujo_quadro_saiu_sem_ela():
    discs = {1: Disciplina(1, "A", "A", 4), 2: Disciplina(2, "B", "B", 4)}
    turmas = {1: [Turma(10, 1, (enc("SEG", 8, 10),), "2026/2")],      # o quadro de 2026/2 saiu…
              2: [Turma(20, 2, (enc("SEG", 14, 16),), "2027/1")]}     # …sem a B (que tem turma em 2027/1)
    res = otimizar_plano(discs, {1: [], 2: []}, turmas, set(), "2026/2", ParametrosOtimizacao())
    onde = {i.disciplina_id: s.periodo for s in res.semestres for i in s.itens}
    assert onde == {1: "2026/2", 2: "2027/1"}


def test_pedido_de_periodo_sem_turma_no_quadro_e_ignorado_com_motivo():
    discs = {1: Disciplina(1, "A", "A", 4), 2: Disciplina(2, "B", "B", 4)}
    turmas = {1: [Turma(10, 1, (enc("SEG", 8, 10),), "2026/2")], 2: [Turma(20, 2, (enc("SEG", 14, 16),), "2027/1")]}
    p = ParametrosOtimizacao(preferencias=PreferenciasAluno(fixas={2: "2026/2"}))
    res = otimizar_plano(discs, {1: [], 2: []}, turmas, set(), "2026/2", p)
    assert res.fixas_ignoradas == {2: "sem_turma"}


# ── via HTTP ────────────────────────────────────────────────────────────────
def test_rota_rotina_e_simulacao_trazem_o_veredito(client_logado, curso_pequeno):
    cid = curso_pequeno["id"]
    assert client_logado.get(f"/api/cursos/{cid}/rotina").get_json()["rotina"] is None     # nada bloqueado
    client_logado.put(f"/api/cursos/{cid}/preferencias",
                      json={"indisponiveis": [{"dia": "SEG", "inicio": "07:00", "fim": "12:00"}]})
    r = client_logado.get(f"/api/cursos/{cid}/rotina").get_json()["rotina"]
    # AAA100 só tem turma SEG 08–10: não cabe; as outras têm turma livre
    assert r["nivel"] == "alto" and [x["codigo"] for x in r["nao_cabem"]] == ["AAA100"]


def test_painel_mostra_a_data_das_obrigatorias_quando_o_curso_nao_informa_optativas(client_logado, curso_pequeno):
    cid, d = curso_pequeno["id"], curso_pequeno["disc"]
    plano = {"nome": "P", "semestres": [{"rotulo": "S1", "periodo_letivo": "2027/1",
                                         "itens": [{"disciplina_id": i} for i in d.values()]}]}
    pid = client_logado.post(f"/api/cursos/{cid}/planos", json=plano).get_json()["plano"]["id"]
    pp = client_logado.get(f"/api/cursos/{cid}/painel?plano_id={pid}").get_json()["previsao_plano"]
    assert pp["cartao"]["valor"] in (pp["formatura"], pp["formatura_com_optativas"], pp["so_obrigatorias"])
    assert pp["cartao"]["valor"] is not None
