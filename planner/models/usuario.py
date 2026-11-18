"""Dados individuais do aluno: conta e histórico escolar."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .enums import StatusHistorico, check_enum


class Usuario(db.Model):
    """
    Conta do aluno. A identidade é o e-mail, confirmado pelo Supabase Auth
    (Etapa 5A); o app não guarda senha nem id do provedor.
    """

    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    nome: Mapped[str | None] = mapped_column(String(200))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    historico: Mapped[list["Historico"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan", passive_deletes=True
    )
    planos: Mapped[list["Plano"]] = relationship(  # noqa: F821
        back_populates="usuario", cascade="all, delete-orphan", passive_deletes=True
    )


class Historico(db.Model):
    """
    Uma TENTATIVA do aluno em uma disciplina (N tentativas por disciplina:
    reprovou e cursou de novo = duas linhas).

    `disciplina_id` usa RESTRICT: apagar uma disciplina NÃO pode apagar nem
    deixar órfão o histórico do aluno. Quem quiser removê-la precisa antes
    resolver o histórico explicitamente.
    """

    __tablename__ = "historico"
    __table_args__ = (
        check_enum("status", StatusHistorico, "status_valido"),
        CheckConstraint("nota IS NULL OR (nota >= 0 AND nota <= 100)", name="nota_entre_0_e_100"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), index=True
    )
    disciplina_id: Mapped[int] = mapped_column(
        ForeignKey("disciplina.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(10))
    periodo_letivo: Mapped[str | None] = mapped_column(String(10))
    nota: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False))

    usuario: Mapped["Usuario"] = relationship(back_populates="historico")
    # Sem relationship inversa em Disciplina de propósito: assim o ORM nunca
    # tenta "soltar" o histórico ao apagar a disciplina; o RESTRICT do banco decide.
    disciplina: Mapped["Disciplina"] = relationship()  # noqa: F821
