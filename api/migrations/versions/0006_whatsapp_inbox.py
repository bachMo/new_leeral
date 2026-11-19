"""whatsapp inbox

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-19 17:00:02.634186+00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = ('admin_users', 'admin_sessions', 'whatsapp_threads')


def upgrade() -> None:
    op.create_table('admin_users',
    sa.Column('email', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('failed_attempts', sa.Integer(), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_admin_users')),
    sa.UniqueConstraint('email', name=op.f('uq_admin_users_email'))
    )
    op.create_table('admin_sessions',
    sa.Column('admin_id', sa.UUID(), nullable=False),
    sa.Column('refresh_token_hash', sa.Text(), nullable=False),
    sa.Column('user_agent', sa.Text(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['admin_id'], ['admin_users.id'], name=op.f('fk_admin_sessions_admin_id_admin_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_admin_sessions')),
    sa.UniqueConstraint('refresh_token_hash', name=op.f('uq_admin_sessions_refresh_token_hash'))
    )
    op.create_table('whatsapp_threads',
    sa.Column('channel_id', sa.UUID(), nullable=False),
    sa.Column('wa_phone', sa.Text(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('bot_paused', sa.Boolean(), nullable=False),
    sa.Column('bot_paused_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['channel_id'], ['whatsapp_channels.id'], name=op.f('fk_whatsapp_threads_channel_id_whatsapp_channels'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_whatsapp_threads_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_whatsapp_threads')),
    sa.UniqueConstraint('channel_id', 'wa_phone', name=op.f('uq_whatsapp_threads_channel_id_wa_phone'))
    )
    op.add_column('whatsapp_messages', sa.Column('media_mime', sa.Text(), nullable=True))
    op.add_column('whatsapp_messages', sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('whatsapp_messages', sa.Column('admin_id', sa.UUID(), nullable=True))
    op.create_index('ix_whatsapp_messages_thread_updated', 'whatsapp_messages', ['channel_id', 'wa_phone', 'updated_at'], unique=False)
    op.create_foreign_key(op.f('fk_whatsapp_messages_admin_id_admin_users'), 'whatsapp_messages', 'admin_users', ['admin_id'], ['id'], ondelete='SET NULL')
    for table in NEW_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )
    op.execute(
        "INSERT INTO whatsapp_threads (channel_id, wa_phone, user_id, bot_paused, last_read_at) "
        "SELECT DISTINCT ON (channel_id, wa_phone) channel_id, wa_phone, user_id, false, now() "
        "FROM whatsapp_messages "
        "ORDER BY channel_id, wa_phone, (user_id IS NULL), created_at DESC"
    )


def downgrade() -> None:
    for table in NEW_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.drop_constraint(op.f('fk_whatsapp_messages_admin_id_admin_users'), 'whatsapp_messages', type_='foreignkey')
    op.drop_index('ix_whatsapp_messages_thread_updated', table_name='whatsapp_messages')
    op.drop_column('whatsapp_messages', 'admin_id')
    op.drop_column('whatsapp_messages', 'meta')
    op.drop_column('whatsapp_messages', 'media_mime')
    op.drop_table('whatsapp_threads')
    op.drop_table('admin_sessions')
    op.drop_table('admin_users')
