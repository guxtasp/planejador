"""Base comum dos repositories (padrão Repository)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..extensions import db


class RepositorioBase:
    """
    Dá acesso à sessão do SQLAlchemy e define a política de transação.

    Regras que valem para TODOS os repositories:
      * só consultas e persistência; nenhuma regra de negócio;
      * `adicionar` faz `flush` (o objeto ganha `id`), mas NUNCA `commit`:
        quem decide o limite da transação é o serviço/importador, o que
        permite o commit atômico da importação (Etapa 3C);
      * coleções relacionadas são carregadas com `selectinload` (1 consulta
        extra por relação, em vez de 1 por linha — evita o problema N+1).

    A sessão pode ser injetada (útil em testes); por padrão usa `db.session`.
    """

    def __init__(self, sessao: Session | None = None) -> None:
        self._sessao = sessao

    @property
    def sessao(self) -> Session:
        return self._sessao if self._sessao is not None else db.session

    def adicionar(self, objeto):
        """Registra `objeto` na sessão e atribui `id`, sem encerrar a transação."""
        self.sessao.add(objeto)
        self.sessao.flush()
        return objeto

    def remover(self, objeto) -> None:
        """Marca `objeto` para remoção; as cascatas ficam a cargo do banco."""
        self.sessao.delete(objeto)
        self.sessao.flush()
