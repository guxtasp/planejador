"""Login por link mágico (Etapa 5A): contador de logins em `usuario`.

Escrita à mão (o ambiente de geração não tinha o SQLAlchemy); o teste
`test_migracao_nao_diverge_dos_modelos` confere que bate com o modelo.

Revision ID: a3c91e7b5d20
Revises: 05f7ecdec8d2
Create Date: 2026-11-17 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3c91e7b5d20'
down_revision = '05f7ecdec8d2'
branch_labels = None
depends_on = None


def upgrade():
    # server_default '0': contas que já existirem começam com a versão zero.
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.add_column(sa.Column('versao_login', sa.Integer(), server_default='0', nullable=False))


def downgrade():
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_column('versao_login')
