"""Horários próprios por disciplina do plano (`plano_item.encontros_livres`).

Permite ao aluno montar o calendário sem depender de quadro de horários importado.
Escrita à mão (sem SQLAlchemy no ambiente de geração); `test_migracao_nao_diverge_dos_modelos`
confere que bate com o modelo.

Revision ID: c5e8f1a2b704
Revises: b7d4e2a19c63
Create Date: 2026-11-17 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c5e8f1a2b704'
down_revision = 'b7d4e2a19c63'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('plano_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('encontros_livres', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('plano_item', schema=None) as batch_op:
        batch_op.drop_column('encontros_livres')
