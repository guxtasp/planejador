"""Planos de curso do aluno: semestres e as disciplinas (turmas) escolhidas."""
from __future__ import annotations

from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db


class Plano(db.Model):
    """Um plano nomeado de um aluno para um curso (o aluno pode ter vários)."""

    __tablename__ = "plano"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), index=True
    )
    curso_id: Mapped[int] = mapped_column(
        ForeignKey("curso.id", ondelete="CASCADE"), index=True
    )
    nome: Mapped[str] = mapped_column(String(200))

    usuario: Mapped["Usuario"] = relationship(back_populates="planos")  # noqa: F821
    semestres: Mapped[list["PlanoSemestre"]] = relationship(
        back_populates="plano", cascade="all, delete-orphan", passive_deletes=True,
        order_by="PlanoSemestre.ordem",
    )


class PlanoSemestre(db.Model):
    """Um semestre (coluna) do plano. `ordem` define a sequência."""

    __tablename__ = "plano_semestre"
    __table_args__ = (
        UniqueConstraint("plano_id", "ordem", name="uq_plano_semestre_ordem"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plano_id: Mapped[int] = mapped_column(ForeignKey("plano.id", ondelete="CASCADE"))
    ordem: Mapped[int] = mapped_column()
    label: Mapped[str] = mapped_column(String(50))
    # NULL = semestre "genérico", ainda sem período letivo real (sem turmas).
    periodo_letivo: Mapped[str | None] = mapped_column(String(10))

    plano: Mapped["Plano"] = relationship(back_populates="semestres")
    itens: Mapped[list["PlanoItem"]] = relationship(
        back_populates="semestre", cascade="all, delete-orphan", passive_deletes=True
    )


class PlanoItem(db.Model):
    """
    Disciplina alocada em um semestre do plano (e, opcionalmente, a turma).

    A chave primária é composta: a mesma disciplina não entra duas vezes no
    mesmo semestre. Garantir que `turma` pertence a `disciplina` é regra do
    serviço de planejamento (Etapa 4B).
    """

    __tablename__ = "plano_item"

    semestre_id: Mapped[int] = mapped_column(
        ForeignKey("plano_semestre.id", ondelete="CASCADE"), primary_key=True
    )
    disciplina_id: Mapped[int] = mapped_column(
        ForeignKey("disciplina.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    # Se a turma deixar de existir, o item continua no plano, só sem turma.
    turma_id: Mapped[int | None] = mapped_column(
        ForeignKey("turma.id", ondelete="SET NULL"), index=True
    )

    # Horários que o aluno definiu à mão: [{"dia","inicio","fim"}]. NULL = nenhum.
    # Excludente com `turma_id` (regra do serviço, ver `validar_referencias`).
    encontros_livres: Mapped[list[dict] | None] = mapped_column(JSON)

    semestre: Mapped["PlanoSemestre"] = relationship(back_populates="itens")
    disciplina: Mapped["Disciplina"] = relationship()  # noqa: F821
    turma: Mapped["Turma | None"] = relationship()  # noqa: F821
