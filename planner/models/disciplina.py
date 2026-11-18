"""Catálogo estável do curso: disciplinas e seus requisitos."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .enums import Periodicidade, TipoDisciplina, TipoRequisito, check_enum


class Disciplina(db.Model):
    """Uma disciplina do catálogo. O `codigo` é único apenas DENTRO do curso."""

    __tablename__ = "disciplina"
    __table_args__ = (
        UniqueConstraint("curso_id", "codigo", name="uq_disciplina_curso_codigo"),
        check_enum("tipo", TipoDisciplina, "tipo_valido"),
        CheckConstraint(
            "periodicidade IS NULL OR periodicidade IN ('sempre', 'impar', 'par')",
            name="periodicidade_valida",
        ),
        CheckConstraint("creditos IS NULL OR creditos >= 0", name="creditos_nao_negativos"),
        CheckConstraint("carga_h IS NULL OR carga_h >= 0", name="carga_h_nao_negativa"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Apagar o curso apaga o catálogo dele (o histórico, porém, protege — ver Historico).
    curso_id: Mapped[int] = mapped_column(ForeignKey("curso.id", ondelete="CASCADE"))
    codigo: Mapped[str] = mapped_column(String(30))
    nome: Mapped[str] = mapped_column(String(200))

    creditos: Mapped[int | None] = mapped_column(Integer)
    carga_h: Mapped[int | None] = mapped_column(Integer)
    periodo_sugerido: Mapped[int | None] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(15), default=TipoDisciplina.OBRIGATORIA.value)
    cor: Mapped[str | None] = mapped_column(String(9))  # hex, ex.: "#3b82f6"
    # sempre | impar | par; NULL = oferta desconhecida (ver `Periodicidade`).
    periodicidade: Mapped[str | None] = mapped_column(String(6))

    curso: Mapped["Curso"] = relationship(back_populates="disciplinas")  # noqa: F821
    # Requisitos DESTA disciplina (o que ela exige). Há duas FKs para
    # `disciplina` em Requisito, por isso `foreign_keys` é explícito.
    requisitos: Mapped[list["Requisito"]] = relationship(
        back_populates="disciplina", foreign_keys="Requisito.disciplina_id",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    turmas: Mapped[list["Turma"]] = relationship(  # noqa: F821
        back_populates="disciplina", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Disciplina {self.codigo}>"


class Requisito(db.Model):
    """
    "`disciplina` exige `requerida`".

    `grupo_alt` modela E/OU: requisitos do mesmo tipo com `grupo_alt` vazio são
    todos obrigatórios (AND); os que compartilham o mesmo `grupo_alt` são
    alternativas entre si (OR).

    Observação: o banco não impede um requisito apontar para disciplina de
    OUTRO curso; essa checagem é semântica e fica no importador/serviço (3B).
    """

    __tablename__ = "requisito"
    __table_args__ = (
        UniqueConstraint("disciplina_id", "requisito_id", "tipo", name="uq_requisito_par_tipo"),
        CheckConstraint("disciplina_id <> requisito_id", name="sem_autorrequisito"),
        check_enum("tipo", TipoRequisito, "tipo_valido"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    disciplina_id: Mapped[int] = mapped_column(
        ForeignKey("disciplina.id", ondelete="CASCADE"), index=True
    )
    requisito_id: Mapped[int] = mapped_column(
        ForeignKey("disciplina.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(3))
    grupo_alt: Mapped[str | None] = mapped_column(String(30))

    disciplina: Mapped["Disciplina"] = relationship(
        back_populates="requisitos", foreign_keys=[disciplina_id]
    )
    requerida: Mapped["Disciplina"] = relationship(foreign_keys=[requisito_id])
