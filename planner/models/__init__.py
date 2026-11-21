"""
Modelos SQLAlchemy (Etapa 1A).

Três grupos, seguindo ARQUITETURA.md §4:
  catálogo (estável)  → Curso, Disciplina, Requisito
  oferta (semestral)  → Turma, Encontro
  usuário (individual)→ Usuario, Historico, Plano, PlanoSemestre, PlanoItem

Importar tudo aqui garante que o Alembic e `db.create_all()` enxerguem todas
as tabelas com um único `from planner import models`.
"""
from .curso import Curso
from .disciplina import Disciplina, Requisito
from .enums import DiaSemana, Periodicidade, StatusHistorico, TipoDisciplina, TipoRequisito, Visibilidade
from .oferta import Encontro, Turma
from .plano import Plano, PlanoItem, PlanoSemestre
from .preferencia import PreferenciaAluno
from .usuario import Historico, Usuario

__all__ = [
    "Curso", "Disciplina", "Requisito", "Turma", "Encontro",
    "Usuario", "Historico", "Plano", "PlanoSemestre", "PlanoItem", "PreferenciaAluno",
    "DiaSemana", "Periodicidade", "StatusHistorico", "TipoDisciplina", "TipoRequisito", "Visibilidade",
]
