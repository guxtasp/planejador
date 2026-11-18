"""
Simulador de futuro e sugestão de plano (Peças 3 e 4, parte C).

Só carrega os dados do banco, chama o domínio (`simular_plano`, `otimizar_plano`) e traduz o
resultado. Nada é gravado: quem quiser guardar uma sugestão usa `POST /planos` com o campo `plano`.

Período inicial, nesta ordem (nunca a data do servidor):
  1. o informado no pedido;
  2. o período do primeiro semestre do plano (só na simulação);
  3. o seguinte ao mais recente do histórico do aluno;
  senão, erro 422 pedindo o período.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..api.errors import AppError
from ..domain.historico import aprovadas, cursando
from ..domain.otimizador import ParametrosOtimizacao, otimizar_plano
from ..domain.progresso import calcular_progresso
from ..domain.simulacao import simular_plano
from ..repositories import DisciplinaRepository, HistoricoRepository
from .catalogo_dominio import carregar_catalogo, tentativas_do_dominio
from .cursos import CursoService
from .simulacao_json import (ler_pedido_simulacao, ler_pedido_sugestao, proximo_periodo_livre,
                             serializar_simulacao, serializar_sugestao)

MSG_SEM_PERIODO = "Informe o período em que o plano começa (por exemplo, 2027/1)."


class SimulacaoService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._cursos = CursoService(sessao)
        self._disciplinas = DisciplinaRepository(sessao)
        self._historico = HistoricoRepository(sessao)

    # ── simular o plano que o aluno montou ──────────────────────────────────
    def simular(self, curso_id: int, usuario_id: int, payload) -> dict:
        curso = self._cursos.obter(curso_id, usuario_id)
        semestres, inicial = ler_pedido_simulacao(payload)
        if not any(s.itens for s in semestres):
            raise AppError("O plano está vazio. Adicione disciplinas em Planejamento ou peça uma sugestão.", 422)

        catalogo = carregar_catalogo(self._disciplinas, curso_id, com_turmas=True)
        tentativas = tentativas_do_dominio(self._historico.listar_do_usuario(usuario_id, curso_id))
        inicial = (inicial
                   or next((s.periodo_letivo for s in semestres if s.periodo_letivo), None)
                   or proximo_periodo_livre([t.periodo_letivo for t in tentativas]))
        if inicial is None:
            raise AppError(MSG_SEM_PERIODO, 422)

        sim = simular_plano(
            semestres, inicial, catalogo.disciplinas, catalogo.requisitos, catalogo.turmas,
            curso["max_creditos_semestre"],
            aprovadas=aprovadas(tentativas), cursando=cursando(tentativas),
            creditos_obrigatorios=curso["creditos_obrigatorios"],
            creditos_optativos_exigidos=curso["creditos_optativos_exigidos"],
        )
        return {"periodo_inicial": inicial, **serializar_simulacao(sim, catalogo.disciplinas)}

    # ── sugerir um plano otimizado ──────────────────────────────────────────
    def sugerir(self, curso_id: int, usuario_id: int, payload) -> dict:
        curso = self._cursos.obter(curso_id, usuario_id)
        pedido = ler_pedido_sugestao(payload)

        catalogo = carregar_catalogo(self._disciplinas, curso_id, com_turmas=True)
        tentativas = tentativas_do_dominio(self._historico.listar_do_usuario(usuario_id, curso_id))
        concluidas = aprovadas(tentativas) | cursando(tentativas)

        inicial = pedido["periodo_inicial"] or proximo_periodo_livre([t.periodo_letivo for t in tentativas])
        if inicial is None:
            raise AppError(MSG_SEM_PERIODO, 422)

        desconhecidas = [i for i in pedido["optativas"] if i not in catalogo.disciplinas]
        if desconhecidas:
            raise AppError("Há uma optativa escolhida que não pertence a este curso.", 422)

        # optativas que a pessoa diz já ter feito (ainda não no histórico) valem só para esta sugestão
        feitas = pedido["optativas_feitas"]
        if any(i not in catalogo.disciplinas for i in feitas):
            raise AppError("Há uma optativa marcada como feita que não pertence a este curso.", 422)
        concluidas = concluidas | set(feitas)

        # teto: o menor entre o do curso e o que a pessoa pediu (o que for conhecido)
        tetos = [x for x in (curso["max_creditos_semestre"], pedido["max_creditos"]) if x]
        teto = min(tetos) if tetos else None

        # créditos de optativas que ainda faltam, já descontando as que a pessoa escolheu
        progresso = calcular_progresso(
            catalogo.disciplinas.values(), concluidas,
            curso["creditos_obrigatorios"], curso["creditos_optativos_exigidos"],
        )
        escolhidas = sum(catalogo.disciplinas[i].creditos or 0 for i in pedido["optativas"] if i not in concluidas)
        calculado = max(0, (progresso.optativos_exigidos or 0) - progresso.optativos_validos)
        informado = pedido["optativas_faltando"]
        # o número que a pessoa informa vale; sem ele, o app calcula pelo exigido do curso menos o cumprido
        faltando = max(0, (calculado if informado is None else informado) - escolhidas)

        resultado = otimizar_plano(
            catalogo.disciplinas, catalogo.requisitos, catalogo.turmas, concluidas, inicial,
            ParametrosOtimizacao(max_creditos=teto, semestres_extras=pedido["semestres_extras"],
                                 optativas_faltando=faltando),
            extras=pedido["optativas"],
        )
        saida = serializar_sugestao(resultado, catalogo.disciplinas, f"Sugestão {inicial}")
        if saida.get("viavel"):
            saida["optativas"].update(
                exigidas_pelo_curso=progresso.optativos_exigidos,
                ja_cumpridas=progresso.optativos_validos, calculadas=calculado,
                origem="informado" if informado is not None else "calculado")
        return {"periodo_inicial": inicial, "limite_creditos": teto, **saida}
