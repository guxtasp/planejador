"""
Histórico escolar do aluno (Etapa 5B-2): N tentativas por disciplina.

Cada operação vale só para o usuário informado: tentativa de outra pessoa dá o
mesmo 404 de uma que não existe. O histórico é do ALUNO, não do curso — mas cada
tentativa aponta para uma disciplina, e o curso dela precisa ser acessível.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..api.errors import NotFoundError
from ..extensions import db
from ..models import Historico
from ..repositories import DisciplinaRepository, HistoricoRepository
from .cursos import CursoService
from ..domain.cursos_parecidos import normalizar_codigo
from ..importers.historico_colado import ler_historico_colado
from .historico_json import STATUS_TXT, ler_tentativa, ler_texto_colado, previa_colado_json, serializar_tentativa


class HistoricoService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._sessao = sessao
        self._cursos = CursoService(sessao)
        self._disciplinas = DisciplinaRepository(sessao)
        self._historico = HistoricoRepository(sessao)

    @property
    def sessao(self) -> Session:
        return self._sessao if self._sessao is not None else db.session

    def listar(self, curso_id: int, usuario_id: int) -> list[dict]:
        self._cursos.obter(curso_id, usuario_id)     # valida o acesso ao curso
        tentativas = self._historico.listar_do_usuario(usuario_id, curso_id, com_disciplina=True)
        return [serializar_tentativa(h) for h in tentativas]

    def criar(self, curso_id: int, usuario_id: int, payload) -> dict:
        self._cursos.obter(curso_id, usuario_id)
        dados = ler_tentativa(payload, com_disciplina=True)
        disciplina = self._disciplinas.obter(dados.disciplina_id)
        # Disciplina de outro curso = mesmo erro de disciplina inexistente.
        if disciplina is None or disciplina.curso_id != curso_id:
            raise NotFoundError("Disciplina não encontrada neste curso.")
        h = self._historico.adicionar(Historico(
            usuario_id=usuario_id, disciplina_id=disciplina.id,
            status=dados.status, periodo_letivo=dados.periodo_letivo, nota=dados.nota,
        ))
        self.sessao.commit()
        return serializar_tentativa(h)

    def atualizar(self, curso_id: int, historico_id: int, usuario_id: int, payload) -> dict:
        h = self._obter_do_curso(curso_id, historico_id, usuario_id)
        dados = ler_tentativa(payload, com_disciplina=False)
        h.status, h.periodo_letivo, h.nota = dados.status, dados.periodo_letivo, dados.nota
        self.sessao.commit()
        return serializar_tentativa(h)

    def colar(self, curso_id: int, usuario_id: int, payload) -> dict:
        """
        Tabela colada do sistema acadêmico: prévia (padrão) ou gravação (`confirmar`). Só grava as linhas
        RECONHECIDAS: código do curso, situação entendida e que não repetem uma tentativa já existente
        (mesma disciplina, situação e período) nem outra linha da colagem.
        """
        self._cursos.obter(curso_id, usuario_id)
        texto, confirmar = ler_texto_colado(payload)
        por_codigo = {normalizar_codigo(c): d for c, d in self._disciplinas.mapa_por_codigo(curso_id).items()}
        vistas = {(h.disciplina_id, h.status, h.periodo_letivo)
                  for h in self._historico.listar_do_usuario(usuario_id, curso_id)}
        linhas, novas = [], []
        for x in ler_historico_colado(texto):
            d = por_codigo.get(x.codigo)
            item = {"numero": x.numero, "texto": x.texto, "codigo": x.codigo, "periodo_letivo": x.periodo_letivo,
                    "status": x.status, "status_txt": STATUS_TXT.get(x.status), "nota": float(x.nota) if x.nota is not None else None,
                    "disciplina": {"id": d.id, "codigo": d.codigo, "nome": d.nome} if d else None}
            if x.problema:
                item.update(resultado="nao_entendida", motivo=x.problema)
            elif d is None:
                item.update(resultado="nao_encontrada", motivo=f"{x.codigo} não é uma disciplina deste curso.")
            elif (d.id, x.status, x.periodo_letivo) in vistas:
                item.update(resultado="duplicada", motivo="Já está no histórico (ou repetida na colagem).")
            else:
                vistas.add((d.id, x.status, x.periodo_letivo))
                item.update(resultado="reconhecida", motivo=None)
                novas.append((d, x))
            linhas.append(item)
        if not confirmar:
            return previa_colado_json(linhas, None)
        for d, x in novas:
            self._historico.adicionar(Historico(usuario_id=usuario_id, disciplina_id=d.id, status=x.status,
                                                periodo_letivo=x.periodo_letivo, nota=x.nota))
        self.sessao.commit()
        return previa_colado_json(linhas, len(novas))

    def remover(self, curso_id: int, historico_id: int, usuario_id: int) -> None:
        self._historico.remover(self._obter_do_curso(curso_id, historico_id, usuario_id))
        self.sessao.commit()

    def _obter_do_curso(self, curso_id: int, historico_id: int, usuario_id: int) -> Historico:
        self._cursos.obter(curso_id, usuario_id)
        h = self._historico.obter_do_usuario(historico_id, usuario_id)
        if h is None or h.disciplina.curso_id != curso_id:
            raise NotFoundError("Registro não encontrado.")
        return h
