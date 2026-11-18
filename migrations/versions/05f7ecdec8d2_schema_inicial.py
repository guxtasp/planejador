"""Schema inicial (Etapa 1A): catálogo, oferta e dados do usuário.

Gerada pelo Alembic e revisada à mão; as tabelas seguem docs/ARQUITETURA.md §4.

Revision ID: 05f7ecdec8d2
Revises: 
Create Date: 2026-11-17 12:19:04.435081

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '05f7ecdec8d2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('usuario',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_usuario')),
    sa.UniqueConstraint('email', name=op.f('uq_usuario_email'))
    )
    op.create_table('curso',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=False),
    sa.Column('instituicao', sa.String(length=200), nullable=True),
    sa.Column('versao_matriz', sa.String(length=50), nullable=True),
    sa.Column('creditos_obrigatorios', sa.Integer(), nullable=True),
    sa.Column('creditos_optativos_exigidos', sa.Integer(), nullable=True),
    sa.Column('ch_total', sa.Integer(), nullable=True),
    sa.Column('max_creditos_semestre', sa.Integer(), nullable=True),
    sa.Column('duracao_semestres', sa.Integer(), nullable=True),
    sa.Column('dias_letivos', sa.JSON(), nullable=True),
    sa.Column('visibilidade', sa.String(length=10), server_default='privado', nullable=False),
    sa.Column('dono_id', sa.Integer(), nullable=True),
    sa.CheckConstraint("visibilidade IN ('privado', 'publico')", name=op.f('ck_curso_visibilidade_valida')),
    sa.ForeignKeyConstraint(['dono_id'], ['usuario.id'], name=op.f('fk_curso_dono_id_usuario'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_curso'))
    )
    with op.batch_alter_table('curso', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_curso_dono_id'), ['dono_id'], unique=False)

    op.create_table('disciplina',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('curso_id', sa.Integer(), nullable=False),
    sa.Column('codigo', sa.String(length=30), nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=False),
    sa.Column('creditos', sa.Integer(), nullable=True),
    sa.Column('carga_h', sa.Integer(), nullable=True),
    sa.Column('periodo_sugerido', sa.Integer(), nullable=True),
    sa.Column('tipo', sa.String(length=15), nullable=False),
    sa.Column('cor', sa.String(length=9), nullable=True),
    sa.CheckConstraint("tipo IN ('obrigatoria', 'optativa', 'eletiva')", name=op.f('ck_disciplina_tipo_valido')),
    sa.CheckConstraint('carga_h IS NULL OR carga_h >= 0', name=op.f('ck_disciplina_carga_h_nao_negativa')),
    sa.CheckConstraint('creditos IS NULL OR creditos >= 0', name=op.f('ck_disciplina_creditos_nao_negativos')),
    sa.ForeignKeyConstraint(['curso_id'], ['curso.id'], name=op.f('fk_disciplina_curso_id_curso'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_disciplina')),
    sa.UniqueConstraint('curso_id', 'codigo', name='uq_disciplina_curso_codigo')
    )
    op.create_table('plano',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('curso_id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=False),
    sa.ForeignKeyConstraint(['curso_id'], ['curso.id'], name=op.f('fk_plano_curso_id_curso'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], name=op.f('fk_plano_usuario_id_usuario'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_plano'))
    )
    with op.batch_alter_table('plano', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_plano_curso_id'), ['curso_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_plano_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('historico',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('disciplina_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('periodo_letivo', sa.String(length=10), nullable=True),
    sa.Column('nota', sa.Numeric(precision=5, scale=2, asdecimal=False), nullable=True),
    sa.CheckConstraint("status IN ('aprovado', 'reprovado', 'cursando')", name=op.f('ck_historico_status_valido')),
    sa.CheckConstraint('nota IS NULL OR (nota >= 0 AND nota <= 100)', name=op.f('ck_historico_nota_entre_0_e_100')),
    sa.ForeignKeyConstraint(['disciplina_id'], ['disciplina.id'], name=op.f('fk_historico_disciplina_id_disciplina'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], name=op.f('fk_historico_usuario_id_usuario'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_historico'))
    )
    with op.batch_alter_table('historico', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_historico_disciplina_id'), ['disciplina_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_historico_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('plano_semestre',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('plano_id', sa.Integer(), nullable=False),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=50), nullable=False),
    sa.Column('periodo_letivo', sa.String(length=10), nullable=True),
    sa.ForeignKeyConstraint(['plano_id'], ['plano.id'], name=op.f('fk_plano_semestre_plano_id_plano'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_plano_semestre')),
    sa.UniqueConstraint('plano_id', 'ordem', name='uq_plano_semestre_ordem')
    )
    op.create_table('requisito',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('disciplina_id', sa.Integer(), nullable=False),
    sa.Column('requisito_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=3), nullable=False),
    sa.Column('grupo_alt', sa.String(length=30), nullable=True),
    sa.CheckConstraint("tipo IN ('pre', 'co')", name=op.f('ck_requisito_tipo_valido')),
    sa.CheckConstraint('disciplina_id <> requisito_id', name=op.f('ck_requisito_sem_autorrequisito')),
    sa.ForeignKeyConstraint(['disciplina_id'], ['disciplina.id'], name=op.f('fk_requisito_disciplina_id_disciplina'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['requisito_id'], ['disciplina.id'], name=op.f('fk_requisito_requisito_id_disciplina'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_requisito')),
    sa.UniqueConstraint('disciplina_id', 'requisito_id', 'tipo', name='uq_requisito_par_tipo')
    )
    with op.batch_alter_table('requisito', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_requisito_disciplina_id'), ['disciplina_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_requisito_requisito_id'), ['requisito_id'], unique=False)

    op.create_table('turma',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('disciplina_id', sa.Integer(), nullable=False),
    sa.Column('periodo_letivo', sa.String(length=10), nullable=False),
    sa.Column('codigo_turma', sa.String(length=20), nullable=False),
    sa.Column('docente', sa.String(length=200), nullable=True),
    sa.Column('vagas', sa.Integer(), nullable=True),
    sa.CheckConstraint('vagas IS NULL OR vagas >= 0', name=op.f('ck_turma_vagas_nao_negativas')),
    sa.ForeignKeyConstraint(['disciplina_id'], ['disciplina.id'], name=op.f('fk_turma_disciplina_id_disciplina'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_turma')),
    sa.UniqueConstraint('disciplina_id', 'periodo_letivo', 'codigo_turma', name='uq_turma_oferta')
    )
    with op.batch_alter_table('turma', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_turma_disciplina_id'), ['disciplina_id'], unique=False)

    op.create_table('encontro',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('turma_id', sa.Integer(), nullable=False),
    sa.Column('dia', sa.String(length=3), nullable=False),
    sa.Column('inicio', sa.Time(), nullable=False),
    sa.Column('fim', sa.Time(), nullable=False),
    sa.Column('local', sa.String(length=100), nullable=True),
    sa.CheckConstraint("dia IN ('SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SAB', 'DOM')", name=op.f('ck_encontro_dia_valido')),
    sa.CheckConstraint('inicio < fim', name=op.f('ck_encontro_inicio_antes_do_fim')),
    sa.ForeignKeyConstraint(['turma_id'], ['turma.id'], name=op.f('fk_encontro_turma_id_turma'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_encontro'))
    )
    with op.batch_alter_table('encontro', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_encontro_turma_id'), ['turma_id'], unique=False)

    op.create_table('plano_item',
    sa.Column('semestre_id', sa.Integer(), nullable=False),
    sa.Column('disciplina_id', sa.Integer(), nullable=False),
    sa.Column('turma_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['disciplina_id'], ['disciplina.id'], name=op.f('fk_plano_item_disciplina_id_disciplina'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['semestre_id'], ['plano_semestre.id'], name=op.f('fk_plano_item_semestre_id_plano_semestre'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['turma_id'], ['turma.id'], name=op.f('fk_plano_item_turma_id_turma'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('semestre_id', 'disciplina_id', name=op.f('pk_plano_item'))
    )
    with op.batch_alter_table('plano_item', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_plano_item_disciplina_id'), ['disciplina_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_plano_item_turma_id'), ['turma_id'], unique=False)



def downgrade():
    with op.batch_alter_table('plano_item', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_plano_item_turma_id'))
        batch_op.drop_index(batch_op.f('ix_plano_item_disciplina_id'))

    op.drop_table('plano_item')
    with op.batch_alter_table('encontro', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_encontro_turma_id'))

    op.drop_table('encontro')
    with op.batch_alter_table('turma', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_turma_disciplina_id'))

    op.drop_table('turma')
    with op.batch_alter_table('requisito', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_requisito_requisito_id'))
        batch_op.drop_index(batch_op.f('ix_requisito_disciplina_id'))

    op.drop_table('requisito')
    op.drop_table('plano_semestre')
    with op.batch_alter_table('historico', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_historico_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_historico_disciplina_id'))

    op.drop_table('historico')
    with op.batch_alter_table('plano', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_plano_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_plano_curso_id'))

    op.drop_table('plano')
    op.drop_table('disciplina')
    with op.batch_alter_table('curso', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_curso_dono_id'))

    op.drop_table('curso')
    op.drop_table('usuario')
