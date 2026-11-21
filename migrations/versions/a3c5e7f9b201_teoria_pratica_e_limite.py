"""Turma teórica/prática separadas e créditos fora do limite do semestre.

- `turma.componente`: NULL (turma completa) | teorica | pratica;
- `plano_item.turma_pratica_id`: a prática escolhida quando a disciplina tem as duas partes;
- `disciplina.conta_no_limite`: False = os créditos não entram no limite de créditos do semestre.

Escrita à mão; `test_migracao_nao_diverge_dos_modelos` confere.

Revision ID: a3c5e7f9b201
Revises: f1b2c3d4e5f6
Create Date: 2026-11-21 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a3c5e7f9b201'
down_revision = 'f1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('turma', schema=None) as batch_op:
        batch_op.add_column(sa.Column('componente', sa.String(length=10), nullable=True))
        batch_op.create_check_constraint(
            'componente_valido', "componente IS NULL OR componente IN ('teorica', 'pratica')")
    with op.batch_alter_table('plano_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('turma_pratica_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_plano_item_turma_pratica_id_turma'), 'turma',
                                    ['turma_pratica_id'], ['id'], ondelete='SET NULL')
    with op.batch_alter_table('disciplina', schema=None) as batch_op:
        batch_op.add_column(sa.Column('conta_no_limite', sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade():
    with op.batch_alter_table('disciplina', schema=None) as batch_op:
        batch_op.drop_column('conta_no_limite')
    with op.batch_alter_table('plano_item', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_plano_item_turma_pratica_id_turma'), type_='foreignkey')
        batch_op.drop_column('turma_pratica_id')
    with op.batch_alter_table('turma', schema=None) as batch_op:
        batch_op.drop_constraint('componente_valido', type_='check')
        batch_op.drop_column('componente')
