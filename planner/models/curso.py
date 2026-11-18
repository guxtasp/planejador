"""Curso: o contêiner de um catálogo acadêmico (disciplinas e ofertas)."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .enums import Visibilidade, check_enum


class Curso(db.Model):
    """
    Um curso/matriz curricular.

    Princípio do projeto: `NULL` = desconhecido, nunca zero. Só `nome` é
    obrigatório; o resto pode ser preenchido depois (ex.: via importação CSV).
    """

    __tablename__ = "curso"
    __table_args__ = (
        check_enum("visibilidade", Visibilidade, "visibilidade_valida"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    instituicao: Mapped[str | None] = mapped_column(String(200))
    versao_matriz: Mapped[str | None] = mapped_column(String(50))

    creditos_obrigatorios: Mapped[int | None] = mapped_column(Integer)
    # "X créditos de uma lista de optativas" (decisão em ARQUITETURA.md §6).
    creditos_optativos_exigidos: Mapped[int | None] = mapped_column(Integer)
    ch_total: Mapped[int | None] = mapped_column(Integer)
    max_creditos_semestre: Mapped[int | None] = mapped_column(Integer)
    duracao_semestres: Mapped[int | None] = mapped_column(Integer)

    # Lista JSON de dias, ex.: ["SEG","TER","QUA","QUI","SEX"]. NULL = a grade
    # do calendário é derivada dos encontros cadastrados (Etapa 4B).
    dias_letivos: Mapped[list[str] | None] = mapped_column(JSON)

    visibilidade: Mapped[str] = mapped_column(
        String(10), default=Visibilidade.PRIVADO.value,
        server_default=Visibilidade.PRIVADO.value,
    )
    # Se o dono for removido, o curso permanece (sem dono) em vez de sumir.
    dono_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="SET NULL"), index=True
    )

    # `passive_deletes`: quem apaga em cascata é o BANCO (ON DELETE CASCADE),
    # sem o ORM carregar milhares de linhas só para removê-las.
    disciplinas: Mapped[list["Disciplina"]] = relationship(  # noqa: F821
        back_populates="curso", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Curso {self.id} {self.nome!r}>"
