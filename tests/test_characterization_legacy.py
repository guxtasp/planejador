"""
Testes de CARACTERIZAÇÃO do app original.

Objetivo: congelar o comportamento atual antes de refatorar. Testes marcados
com `legacy_bug` descrevem defeitos conhecidos (ver docs/DIAGNOSTICO.md);
eles PASSAM hoje justamente porque o bug existe, e devem ser invertidos na
etapa que o corrigir (Etapa 2: motor de regras).
"""
import pytest


# ── helpers ────────────────────────────────────────────────────────────────
def _disc_id(legacy, codigo):
    with legacy.get_db() as conn:
        return conn.execute(
            "SELECT id FROM disciplinas WHERE codigo=?", (codigo,)
        ).fetchone()[0]


def _semestre_ids(client):
    """IDs dos semestres do plano padrão criado pelo seed."""
    plano = client.get("/api/planos").get_json()[0]
    return [s["id"] for s in plano["semestres"]]


# ── comportamento que deve ser PRESERVADO ──────────────────────────────────
def test_conflito_de_horario_e_detectado(legacy):
    """INF110 e EST105 colidem em SEG 16-18 e em QUI 14-16."""
    conflitos = legacy.check_horario_conflict(
        _disc_id(legacy, "INF110"), [_disc_id(legacy, "EST105")]
    )
    assert {c["dia"] for c in conflitos} == {"SEG", "QUI"}


def test_prerequisito_pendente_sem_historico(legacy):
    ok, pre, _co = legacy.check_prereqs(_disc_id(legacy, "INF112"), set())
    assert ok is False
    assert [p["codigo"] for p in pre] == ["INF110"]


def test_planejador_insere_e_avisa_em_vez_de_bloquear(legacy_client, legacy):
    """Comportamento de UX a manter: o item entra no plano mesmo com avisos."""
    sem1 = _semestre_ids(legacy_client)[0]
    resp = legacy_client.post(
        f"/api/semestres/{sem1}/disciplinas",
        json={"disciplina_id": _disc_id(legacy, "INF112")},
    )
    assert resp.get_json()["ok"] is True
    assert resp.get_json()["avisos"]["prereqs_pendentes"]


# ── defeitos CONHECIDOS (devem mudar na Etapa 2/1) ─────────────────────────
@pytest.mark.legacy_bug
def test_seed_tem_49_disciplinas_e_readme_diz_40(legacy):
    """README promete 40 disciplinas / 8 períodos; o seed tem 49 em 9 grupos."""
    with legacy.get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM disciplinas").fetchone()[0]
    assert total == 49


@pytest.mark.legacy_bug
def test_historico_do_seed_nasce_vazio(legacy_client):
    """Bug #9: o seed referencia códigos (MAT001…) que não existem na matriz."""
    assert legacy_client.get("/api/historico").get_json() == []


@pytest.mark.legacy_bug
def test_prerequisito_ignora_o_proprio_plano(legacy_client, legacy):
    """
    Bug #5: planejar INF110 no semestre 1 e INF112 (que exige INF110) no
    semestre 2 AINDA acusa pré-requisito pendente, pois só o histórico conta.
    """
    sem1, sem2 = _semestre_ids(legacy_client)[:2]
    legacy_client.post(
        f"/api/semestres/{sem1}/disciplinas",
        json={"disciplina_id": _disc_id(legacy, "INF110")},
    )
    resp = legacy_client.post(
        f"/api/semestres/{sem2}/disciplinas",
        json={"disciplina_id": _disc_id(legacy, "INF112")},
    )
    pendentes = resp.get_json()["avisos"]["prereqs_pendentes"]
    assert [p["codigo"] for p in pendentes] == ["INF110"]


@pytest.mark.legacy_bug
def test_historico_aceita_um_registro_por_disciplina(legacy_client, legacy):
    """Bug #4: reprovação seguida de aprovação sobrescreve em vez de acumular."""
    did = _disc_id(legacy, "INF110")
    legacy_client.post("/api/historico", json={"disciplina_id": did, "status": "reprovado"})
    legacy_client.post("/api/historico", json={"disciplina_id": did, "status": "aprovado"})
    registros = legacy_client.get("/api/historico").get_json()
    assert len(registros) == 1


@pytest.mark.legacy_bug
def test_limite_de_sobrecarga_fixo_em_28(legacy_client, legacy):
    """Regra hardcoded: > 28 créditos é sobrecarga, para qualquer curso."""
    sem1 = _semestre_ids(legacy_client)[0]
    for cod in ("INF110", "INF112", "MAT135", "INF213", "INF150", "INF191", "MAT131"):
        legacy_client.post(
            f"/api/semestres/{sem1}/disciplinas", json={"disciplina_id": _disc_id(legacy, cod)}
        )
    resp = legacy_client.get(f"/api/validar_semestre/{sem1}").get_json()
    assert resp["creditos_total"] == 32
    assert resp["sobrecarga"] is True


@pytest.mark.legacy_bug
def test_progresso_conta_optativas_como_obrigatorias(legacy_client, legacy):
    """Regra acoplada: total de créditos = soma de TODAS as disciplinas."""
    stats = legacy_client.get("/api/assistente").get_json()["stats"]
    with legacy.get_db() as conn:
        soma_tudo = conn.execute("SELECT SUM(creditos) FROM disciplinas").fetchone()[0]
        soma_optativas = conn.execute(
            "SELECT SUM(creditos) FROM disciplinas WHERE periodo=9"
        ).fetchone()[0]
    assert stats["total_creditos"] == soma_tudo
    assert soma_optativas > 0  # optativas entraram no denominador
