"""Periodicidade de oferta da disciplina (`disciplina.periodicidade`).

`sempre` | `impar` | `par`; NULL = desconhecida. Alimenta o simulador de planejamento
(uma disciplina só de períodos ímpares não pode cair num semestre par).
Escrita à mão; `test_migracao_nao_diverge_dos_modelos` confere que bate com o modelo.

Revision ID: d6f2a3b8c915
Revises: c5e8f1a2b704
Create Date: 2026-11-18 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd6f2a3b8c915'
down_revision = 'c5e8f1a2b704'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('disciplina', schema=None) as batch_op:
        batch_op.add_column(sa.Column('periodicidade', sa.String(length=6), nullable=True))
        batch_op.create_check_constraint(
            batch_op.f('ck_disciplina_periodicidade_valida'),
            "periodicidade IS NULL OR periodicidade IN ('sempre', 'impar', 'par')",
        )


def downgrade():
    with op.batch_alter_table('disciplina', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('ck_disciplina_periodicidade_valida'), type_='check')
        batch_op.drop_column('periodicidade')
