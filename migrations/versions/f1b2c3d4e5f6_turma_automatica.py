"""Turma escolhida automaticamente no plano (`plano_item.turma_auto`).

True = o Rumo escolheu a turma (melhor combinação do semestre) e pode trocá-la quando o semestre muda;
False = o aluno escolheu (fica fixa). Escrita à mão; `test_migracao_nao_diverge_dos_modelos` confere.

Revision ID: f1b2c3d4e5f6
Revises: e7a4b9c2d013
Create Date: 2026-11-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f1b2c3d4e5f6'
down_revision = 'e7a4b9c2d013'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('plano_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('turma_auto', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    with op.batch_alter_table('plano_item', schema=None) as batch_op:
        batch_op.drop_column('turma_auto')
