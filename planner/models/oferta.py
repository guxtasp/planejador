"""Oferta semestral: turmas de uma disciplina e seus encontros semanais."""
from __future__ import annotations

from datetime import time

from sqlalchemy import CheckConstraint, ForeignKey, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .enums import DiaSemana, check_enum


class Turma(db.Model):
    """Uma turma (alternativa de matrícula) de uma disciplina em um período letivo."""

    __tablename__ = "turma"
    __table_args__ = (
        UniqueConstraint(
            "disciplina_id", "periodo_letivo", "codigo_turma", name="uq_turma_oferta"
        ),
        CheckConstraint("vagas IS NULL OR vagas >= 0", name="vagas_nao_negativas"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    disciplina_id: Mapped[int] = mapped_column(
        ForeignKey("disciplina.id", ondelete="CASCADE"), index=True
    )
    periodo_letivo: Mapped[str] = mapped_column(String(10))  # ex.: "2026/1"
    codigo_turma: Mapped[str] = mapped_column(String(20))    # ex.: "T1", "P2"
    docente: Mapped[str | None] = mapped_column(String(200))
    vagas: Mapped[int | None] = mapped_column()

    disciplina: Mapped["Disciplina"] = relationship(back_populates="turmas")  # noqa: F821
    encontros: Mapped[list["Encontro"]] = relationship(
        back_populates="turma", cascade="all, delete-orphan", passive_deletes=True,
        order_by="Encontro.dia, Encontro.inicio",
    )


class Encontro(db.Model):
    """
    Um horário semanal da turma. TODOS os encontros de uma turma são
    obrigatórios (teoria e prática combinadas — ver ARQUITETURA.md §6).
    """

    __tablename__ = "encontro"
    __table_args__ = (
        check_enum("dia", DiaSemana, "dia_valido"),
        CheckConstraint("inicio < fim", name="inicio_antes_do_fim"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    turma_id: Mapped[int] = mapped_column(
        ForeignKey("turma.id", ondelete="CASCADE"), index=True
    )
    dia: Mapped[str] = mapped_column(String(3))
    inicio: Mapped[time] = mapped_column(Time)
    fim: Mapped[time] = mapped_column(Time)
    local: Mapped[str | None] = mapped_column(String(100))

    turma: Mapped["Turma"] = relationship(back_populates="encontros")
