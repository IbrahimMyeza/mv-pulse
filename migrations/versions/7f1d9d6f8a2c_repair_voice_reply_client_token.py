"""Repair voice reply client token for legacy local databases

Revision ID: 7f1d9d6f8a2c
Revises: 2513dc99da7b
Create Date: 2026-04-19 19:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7f1d9d6f8a2c'
down_revision = '2513dc99da7b'
branch_labels = None
depends_on = None


def _column_names(inspector, table_name):
    return {column['name'] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name):
    return {index['name'] for index in inspector.get_indexes(table_name)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if 'voice_reply' not in table_names:
        return

    column_names = _column_names(inspector, 'voice_reply')
    if 'client_token' not in column_names:
        with op.batch_alter_table('voice_reply', schema=None) as batch_op:
            batch_op.add_column(sa.Column('client_token', sa.String(length=128), nullable=True))

    inspector = sa.inspect(bind)
    index_names = _index_names(inspector, 'voice_reply')
    if 'ix_voice_reply_client_token' not in index_names:
        with op.batch_alter_table('voice_reply', schema=None) as batch_op:
            batch_op.create_index('ix_voice_reply_client_token', ['client_token'], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if 'voice_reply' not in table_names:
        return

    index_names = _index_names(inspector, 'voice_reply')
    if 'ix_voice_reply_client_token' in index_names:
        with op.batch_alter_table('voice_reply', schema=None) as batch_op:
            batch_op.drop_index('ix_voice_reply_client_token')

    inspector = sa.inspect(bind)
    column_names = _column_names(inspector, 'voice_reply')
    if 'client_token' in column_names:
        with op.batch_alter_table('voice_reply', schema=None) as batch_op:
            batch_op.drop_column('client_token')