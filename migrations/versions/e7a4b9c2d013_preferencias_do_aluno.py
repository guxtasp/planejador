"""Preferências do aluno por curso (`preferencia_aluno`).

Disponibilidade, turno, dias livres, teto por período, trancamento, disciplinas pesadas e grupos
"cursar junto", em JSON já validado. Um registro por (usuario, curso).
Escrita à mão; `test_migracao_nao_diverge_dos_modelos` confere que bate com o modelo.

Revision ID: e7a4b9c2d013
Revises: d6f2a3b8c915
Create Date: 2026-11-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e7a4b9c2d013'
down_revision = 'd6f2a3b8c915'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'preferencia_aluno',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('curso_id', sa.Integer(), nullable=False),
        sa.Column('dados', sa.JSON(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'),
                  nullable=False),
        sa.ForeignKeyConstraint(['curso_id'], ['curso.id'], name=op.f('fk_preferencia_aluno_curso_id_curso'),
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], name=op.f('fk_preferencia_aluno_usuario_id_usuario'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_preferencia_aluno')),
        sa.UniqueConstraint('usuario_id', 'curso_id', name='uq_preferencia_usuario_curso'),
    )
    with op.batch_alter_table('preferencia_aluno', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_preferencia_aluno_curso_id'), ['curso_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_preferencia_aluno_usuario_id'), ['usuario_id'], unique=False)


def downgrade():
    with op.batch_alter_table('preferencia_aluno', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_preferencia_aluno_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_preferencia_aluno_curso_id'))
    op.drop_table('preferencia_aluno')
