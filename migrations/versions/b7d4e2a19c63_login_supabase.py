"""Login pelo Supabase (Etapa 5B): remove o contador do link mágico próprio.

O link mágico próprio (5A) precisava de `usuario.versao_login` para valer uma vez
só. Com o Supabase Auth essa responsabilidade é dele, e a coluna deixa de existir.
Escrita à mão (o ambiente de geração não tinha o SQLAlchemy); o teste
`test_migracao_nao_diverge_dos_modelos` confere que bate com o modelo.

Revision ID: b7d4e2a19c63
Revises: a3c91e7b5d20
Create Date: 2026-11-17 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7d4e2a19c63'
down_revision = 'a3c91e7b5d20'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_column('versao_login')


def downgrade():
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.add_column(sa.Column('versao_login', sa.Integer(), server_default='0', nullable=False))
