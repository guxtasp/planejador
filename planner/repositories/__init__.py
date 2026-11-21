"""
Repositories: único lugar com consultas ao banco (Etapa 1B).

Cada repository cuida de um modelo, só consulta/persiste e não faz `commit`
(ver `base.RepositorioBase`). Regras de negócio ficam em `domain/` e `services/`.
"""
from .base import RepositorioBase
from .curso import CursoRepository
from .disciplina import DisciplinaRepository
from .historico import HistoricoRepository
from .plano import PlanoRepository
from .preferencia import PreferenciaRepository
from .requisito import RequisitoRepository
from .turma import TurmaRepository
from .usuario import UsuarioRepository

__all__ = [
    "RepositorioBase", "CursoRepository", "DisciplinaRepository", "HistoricoRepository",
    "PlanoRepository", "PreferenciaRepository", "RequisitoRepository", "TurmaRepository", "UsuarioRepository",
]
