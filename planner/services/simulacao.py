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
from ..domain.historico import aprovadas, contagem_de_resultados, cursando, ja_reprovadas
from ..domain.monte_carlo import taxa_de_aprovacao
from ..domain.otimizador import ParametrosOtimizacao, avaliar_sugestao, otimizar_plano
from ..domain.preferencias import PreferenciasAluno
from ..domain.prazo import ingresso_do_aluno
from ..domain.previsao import somar_periodos
from ..domain.progresso import calcular_progresso
from ..domain.semana import DIAS_UTEIS, rotina_comporta
from ..domain.entidades import TIPO_OBRIGATORIA
from ..domain.simulacao import simular_plano
from ..repositories import DisciplinaRepository, HistoricoRepository
from .catalogo_dominio import carregar_catalogo, tentativas_do_dominio
from .cursos import CursoService
from .preferencias import PreferenciaService
from ..domain.optativas import optativas_que_cabem
from ..domain.juntas import candidatas_a_juntas
from .simulacao_json import (candidatas_juntas_json, indicadores_da_sugestao, ler_pedido_optativas, mensagem_efeito_pedidos,
                             optativas_que_cabem_json)
from .simulacao_json import (ler_pedido_simulacao, ler_pedido_sugestao, ler_preferencias, monte_carlo_json,
                             prazo_json, proximo_periodo_livre, rotina_json, serializar_simulacao, serializar_sugestao)

MSG_SEM_PERIODO = "Informe o período em que o plano começa (por exemplo, 2027/1)."


def _chave(periodo: str) -> tuple[int, int]:
    ano, n = periodo.split("/")
    return int(ano), int(n)


class _Contexto:
    """O que simular e sugerir precisam do aluno: preferências, pesadas, taxa e ingresso."""

    def __init__(self, payload, catalogo, tentativas, curso, guardadas: dict | None = None) -> None:
        # sem "preferencias" no pedido, valem as guardadas (o aluno não precisa informar de novo)
        if not (isinstance(payload, dict) and "preferencias" in payload) and guardadas:
            payload = {**(payload or {}), "preferencias": guardadas}
        pref = ler_preferencias(payload)
        marcadas = pref["pesadas_marcadas"]
        if any(i not in catalogo.disciplinas for i in marcadas):
            raise AppError("Há uma disciplina marcada como pesada que não pertence a este curso.", 422,
                           {"campo": "pesadas"})
        # optativas da rotina: as feitas fora do histórico contam como cumpridas; "ainda preciso de N"
        # (se informado) vale no lugar do cálculo pelo curso. Simulação e sugestão usam os MESMOS números.
        feitas_fora = set(pref["optativas_feitas"])
        if any(i not in catalogo.disciplinas for i in feitas_fora):
            raise AppError("Há uma optativa marcada como feita que não pertence a este curso.", 422,
                           {"campo": "optativas_feitas"})
        self.optativas_feitas = frozenset(feitas_fora)
        self.optativas_faltando = pref["optativas_faltando"]
        reprovadas = ja_reprovadas(tentativas)
        self.reprovadas = reprovadas
        self.marcadas = frozenset(marcadas)
        self.preferencias = PreferenciasAluno(
            semana=pref["semana"], teto_por_periodo=pref["teto_por_periodo"],
            periodos_pulados=pref["periodos_pulados"], max_pesadas=pref["max_pesadas"],
            pesadas=frozenset(reprovadas) | self.marcadas,
            juntas=tuple(g for g in pref["juntas"] if all(i in catalogo.disciplinas for i in g.disciplinas)),
            fixas={d: per for d, per in pref["fixas"].items() if d in catalogo.disciplinas},
        )
        self.taxa = taxa_de_aprovacao(*contagem_de_resultados(tentativas))
        self.fator = pref["fator_prazo"]
        self.simulacoes = pref["simulacoes"]
        self.duracao = curso.get("duracao_semestres")
        dias = [d for d in (curso.get("dias_letivos") or []) if d in DIAS_UTEIS + ("SAB", "DOM")]
        self.dias_base = tuple(dias) or DIAS_UTEIS
        self._informado = pref["periodo_ingresso"]
        self._periodos = [t.periodo_letivo for t in tentativas]
        self._tem_historico = bool(tentativas)

    def ingresso(self, inicial: str) -> tuple[str | None, str | None]:
        return ingresso_do_aluno(self._informado, self._periodos, self._tem_historico, inicial)

    def preferencias_json(self, disciplinas) -> dict:
        ref = lambda i: {"id": i, "codigo": disciplinas[i].codigo, "nome": disciplinas[i].nome}
        return {
            "pesadas": [{**ref(i), "motivo": "reprovada" if i in self.reprovadas else "marcada"}
                        for i in sorted(self.preferencias.pesadas) if i in disciplinas],
            "max_pesadas": self.preferencias.max_pesadas,
            "teto_por_periodo": dict(self.preferencias.teto_por_periodo),
            "periodos_pulados": sorted(self.preferencias.periodos_pulados, key=_chave),
            "fator_prazo_maximo": self.fator,
        }


def _rotina(catalogo, concluidas, ctx: "_Contexto") -> dict | None:
    """Obrigatórias que faltam × horários bloqueados: uma resposta só para "dá pra trabalhar?"."""
    semana = ctx.preferencias.semana
    faltam = [i for i, d in catalogo.disciplinas.items() if d.tipo == TIPO_OBRIGATORIA and i not in concluidas]
    return rotina_json(rotina_comporta(faltam, catalogo.turmas, semana), catalogo.disciplinas,
                       bool(semana and semana.indisponiveis))


class SimulacaoService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._cursos = CursoService(sessao)
        self._disciplinas = DisciplinaRepository(sessao)
        self._historico = HistoricoRepository(sessao)
        self._preferencias = PreferenciaService(sessao)

    # ── simular o plano que o aluno montou ──────────────────────────────────
    def simular(self, curso_id: int, usuario_id: int, payload) -> dict:
        curso = self._cursos.obter(curso_id, usuario_id)
        semestres, inicial = ler_pedido_simulacao(payload)
        if not any(s.itens for s in semestres):
            raise AppError("O plano está vazio. Adicione disciplinas em Planejamento ou peça uma sugestão.", 422)

        catalogo = carregar_catalogo(self._disciplinas, curso_id, com_turmas=True)
        tentativas = tentativas_do_dominio(self._historico.listar_do_usuario(usuario_id, curso_id))
        ctx = _Contexto(payload, catalogo, tentativas, curso, self._preferencias.dados(curso_id, usuario_id))
        inicial = (inicial
                   or next((s.periodo_letivo for s in semestres if s.periodo_letivo), None)
                   or proximo_periodo_livre([t.periodo_letivo for t in tentativas]))
        if inicial is None:
            raise AppError(MSG_SEM_PERIODO, 422, {"campo": "periodo_inicial"})

        ingresso, origem = ctx.ingresso(inicial)
        sim = simular_plano(
            semestres, inicial, catalogo.disciplinas, catalogo.requisitos, catalogo.turmas,
            curso["max_creditos_semestre"],
            aprovadas=aprovadas(tentativas) | ctx.optativas_feitas, cursando=cursando(tentativas),
            optativas_informadas=ctx.optativas_faltando,
            creditos_obrigatorios=curso["creditos_obrigatorios"],
            creditos_optativos_exigidos=curso["creditos_optativos_exigidos"],
            preferencias=ctx.preferencias, duracao_semestres=ctx.duracao, fator_prazo=ctx.fator,
            periodo_ingresso=ingresso, taxa=ctx.taxa, ja_reprovadas=ctx.reprovadas,
            n_monte_carlo=ctx.simulacoes, dias_base=ctx.dias_base,
        )
        return {
            "periodo_inicial": inicial, **serializar_simulacao(sim, catalogo.disciplinas),
            "prazo": prazo_json(sim.prazo, ingresso, origem,
                                sim.formatura_para_prazo, not sim.resumo.completo, ctx.fator),
            "preferencias": ctx.preferencias_json(catalogo.disciplinas),
            "rotina": _rotina(catalogo, aprovadas(tentativas) | cursando(tentativas), ctx),
        }

    # ── "dá para cursar o que falta com a minha rotina?" ────────────────────
    def rotina(self, curso_id: int, usuario_id: int) -> dict:
        curso = self._cursos.obter(curso_id, usuario_id)
        catalogo = carregar_catalogo(self._disciplinas, curso_id, com_turmas=True)
        tentativas = tentativas_do_dominio(self._historico.listar_do_usuario(usuario_id, curso_id))
        ctx = _Contexto({}, catalogo, tentativas, curso, self._preferencias.dados(curso_id, usuario_id))
        concluidas = aprovadas(tentativas) | cursando(tentativas) | ctx.optativas_feitas
        return {"rotina": _rotina(catalogo, concluidas, ctx)}

    # ── "cursar junto": candidatas para perguntar ao aluno ──────────────────
    def candidatas_juntas(self, curso_id: int, usuario_id: int) -> dict:
        self._cursos.obter(curso_id, usuario_id)
        catalogo = carregar_catalogo(self._disciplinas, curso_id)
        tentativas = tentativas_do_dominio(self._historico.listar_do_usuario(usuario_id, curso_id))
        guardadas = self._preferencias.dados(curso_id, usuario_id)
        cands = candidatas_a_juntas(catalogo.disciplinas.values(), catalogo.requisitos,
                                    aprovadas(tentativas) | cursando(tentativas))
        return candidatas_juntas_json(cands, catalogo.disciplinas, bool(guardadas.get("juntas_respondida")),
                                      bool(guardadas.get("juntas")))

    # ── optativas que cabem num semestre do plano ───────────────────────────
    def optativas(self, curso_id: int, usuario_id: int, payload) -> dict:
        curso = self._cursos.obter(curso_id, usuario_id)
        semestres, posicao, inicial = ler_pedido_optativas(payload)
        catalogo = carregar_catalogo(self._disciplinas, curso_id, com_turmas=True)
        tentativas = tentativas_do_dominio(self._historico.listar_do_usuario(usuario_id, curso_id))
        ctx = _Contexto({}, catalogo, tentativas, curso, self._preferencias.dados(curso_id, usuario_id))
        inicial = (inicial or next((s.periodo_letivo for s in semestres if s.periodo_letivo), None)
                   or proximo_periodo_livre([t.periodo_letivo for t in tentativas]))
        if inicial is None:
            raise AppError(MSG_SEM_PERIODO, 422, {"campo": "periodo_inicial"})
        periodos, anterior = [], None
        for s in semestres:      # semestre sem período continua a sequência
            p = s.periodo_letivo or (somar_periodos(anterior, 1) if anterior else inicial)
            periodos.append(p)
            anterior = p
        plano = [(p, [i.disciplina_id for i in s.itens]) for p, s in zip(periodos, semestres)]
        periodo = periodos[posicao - 1]
        teto = ctx.preferencias.teto(periodo, curso["max_creditos_semestre"])
        lista = optativas_que_cabem(plano, posicao - 1, catalogo.disciplinas, catalogo.requisitos, catalogo.turmas,
                                    aprovadas(tentativas) | cursando(tentativas), ctx.preferencias.semana, teto)
        por_id = {t.id: t for ts in catalogo.turmas.values() for t in ts}
        return {"posicao": posicao, **optativas_que_cabem_json(lista, catalogo.disciplinas, periodo, teto, por_id)}

    # ── sugerir um plano otimizado ──────────────────────────────────────────
    def sugerir(self, curso_id: int, usuario_id: int, payload) -> dict:
        curso = self._cursos.obter(curso_id, usuario_id)
        pedido = ler_pedido_sugestao(payload)

        catalogo = carregar_catalogo(self._disciplinas, curso_id, com_turmas=True)
        tentativas = tentativas_do_dominio(self._historico.listar_do_usuario(usuario_id, curso_id))
        concluidas = aprovadas(tentativas) | cursando(tentativas)
        ctx = _Contexto(payload, catalogo, tentativas, curso, self._preferencias.dados(curso_id, usuario_id))

        inicial = pedido["periodo_inicial"] or proximo_periodo_livre([t.periodo_letivo for t in tentativas])
        if inicial is None:
            raise AppError(MSG_SEM_PERIODO, 422, {"campo": "periodo_inicial"})

        desconhecidas = [i for i in pedido["optativas"] if i not in catalogo.disciplinas]
        if desconhecidas:
            raise AppError("Há uma optativa escolhida que não pertence a este curso.", 422)

        # optativas que a pessoa diz já ter feito (ainda não no histórico) valem só para esta sugestão
        feitas = set(pedido["optativas_feitas"]) | ctx.optativas_feitas     # do pedido ou da rotina
        if any(i not in catalogo.disciplinas for i in feitas):
            raise AppError("Há uma optativa marcada como feita que não pertence a este curso.", 422)
        concluidas = concluidas | feitas

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
        informado = pedido["optativas_faltando"] if pedido["optativas_faltando"] is not None else ctx.optativas_faltando
        # o número que a pessoa informa vale; sem ele, o app calcula pelo exigido do curso menos o cumprido
        faltando = max(0, (calculado if informado is None else informado) - escolhidas)

        parametros = ParametrosOtimizacao(max_creditos=teto, semestres_extras=pedido["semestres_extras"],
                                          optativas_faltando=faltando, preferencias=ctx.preferencias)
        # o plano aberto no Planejamento entra como ponto de partida: a sugestão não sai pior que ele
        plano_atual = []
        if isinstance(payload, dict) and isinstance(payload.get("plano_atual"), dict):
            plano_atual = [(s.periodo_letivo, [i.disciplina_id for i in s.itens])
                           for s in ler_pedido_simulacao(payload["plano_atual"])[0]]
        resultado = otimizar_plano(
            catalogo.disciplinas, catalogo.requisitos, catalogo.turmas, concluidas, inicial,
            parametros, extras=pedido["optativas"], plano_atual=plano_atual,
        )
        saida = serializar_sugestao(resultado, catalogo.disciplinas, f"Sugestão {inicial}", ctx.preferencias.juntas)
        if resultado.viavel and (resultado.grupos_aplicados or resultado.fixas_respeitadas):
            # os PEDIDOS do aluno (cursar junto, disciplina num período) mudaram a data? compara com a mesma
            # sugestão sem eles e diz o custo em linguagem simples
            from dataclasses import replace
            sem = otimizar_plano(catalogo.disciplinas, catalogo.requisitos, catalogo.turmas, concluidas, inicial,
                                 replace(parametros, preferencias=replace(ctx.preferencias, juntas=(), fixas={})),
                                 extras=pedido["optativas"], plano_atual=plano_atual)
            d = catalogo.disciplinas
            pedidos = [f"{d[x].codigo} em {per}" for x, per in sorted(resultado.fixas_respeitadas.items())]
            pedidos += [" com ".join(d[i].codigo for i in b) for b in resultado.grupos_aplicados]
            saida["pedidos_mensagem"] = mensagem_efeito_pedidos(
                resultado.periodo_fim_com_optativas or (resultado.metricas.periodo_fim if resultado.metricas else None),
                (sem.periodo_fim_com_optativas or sem.metricas.periodo_fim) if sem.viavel and sem.metricas else None,
                pedidos)
        if saida.get("viavel"):
            saida["optativas"].update(
                exigidas_pelo_curso=progresso.optativos_exigidos,
                ja_cumpridas=progresso.optativos_validos, calculadas=calculado,
                origem="informado" if informado is not None else "calculado")
            ingresso, origem = ctx.ingresso(inicial)
            av = avaliar_sugestao(resultado, catalogo.disciplinas, catalogo.requisitos, concluidas, inicial,
                                  parametros, ctx.duracao, ctx.fator, ingresso, ctx.taxa, ctx.reprovadas,
                                  ctx.simulacoes)
            fim = resultado.periodo_fim_com_optativas or (resultado.metricas.periodo_fim if resultado.metricas else None)
            saida["prazo"] = prazo_json(av.prazo, ingresso, origem, fim,
                                        False, ctx.fator)
            saida["monte_carlo"] = monte_carlo_json(av.monte_carlo, lambda i: somar_periodos(inicial, i),
                                                    catalogo.disciplinas)
            saida["metricas"]["dias_livres_media"] = av.dias_livres_media
            saida["indicadores"] = indicadores_da_sugestao(resultado, saida["monte_carlo"], av.dias_livres_media)
        return {"periodo_inicial": inicial, "limite_creditos": teto, **saida,
                "preferencias": ctx.preferencias_json(catalogo.disciplinas),
                "rotina": _rotina(catalogo, concluidas, ctx)}
