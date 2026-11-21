"""Preferências do aluno por curso: disponibilidade, turno, teto por período, trancamento, pesadas e
disciplinas que quer cursar juntas. Guardadas para valerem em Simulador, Sugestão, Planejamento e
Calendário sem perguntar de novo."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class PreferenciaAluno(db.Model):
    """Um registro por (aluno, curso). `dados` é o JSON já validado por `simulacao_json`."""

    __tablename__ = "preferencia_aluno"
    __table_args__ = (UniqueConstraint("usuario_id", "curso_id", name="uq_preferencia_usuario_curso"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    curso_id: Mapped[int] = mapped_column(ForeignKey("curso.id", ondelete="CASCADE"), index=True)
    dados: Mapped[dict] = mapped_column(JSON, default=dict)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
