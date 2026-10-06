"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-06 16:23:03.348177+00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPDATED_AT_FUNCTION = """
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

PLANS = [
    ("free", 0, None, 1, 1, False),
    ("leeral_plus", 500, 30, 5, None, True),
]


def _timestamped_tables() -> list[str]:
    rows = op.get_bind().execute(
        sa.text(
            "SELECT table_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name = 'updated_at'"
        )
    )
    return [row[0] for row in rows]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table('otp_codes',
    sa.Column('phone_number', sa.Text(), nullable=False),
    sa.Column('code_hash', sa.Text(), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_otp_codes'))
    )
    op.create_index('ix_otp_codes_phone_created', 'otp_codes', ['phone_number', 'created_at'], unique=False)
    op.create_table('plans',
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('price_xof', sa.Integer(), nullable=False),
    sa.Column('duration_days', sa.Integer(), nullable=True),
    sa.Column('writings_per_month', sa.Integer(), nullable=False),
    sa.Column('practice_per_day', sa.Integer(), nullable=True),
    sa.Column('document_words', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_plans')),
    sa.UniqueConstraint('code', name=op.f('uq_plans_code'))
    )
    op.create_table('ui_prompts',
    sa.Column('key', sa.Text(), nullable=False),
    sa.Column('language', sa.Text(), nullable=False),
    sa.Column('text_fr', sa.Text(), nullable=False),
    sa.Column('audio_key', sa.Text(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ui_prompts')),
    sa.UniqueConstraint('key', 'language', name=op.f('uq_ui_prompts_key_language'))
    )
    op.create_table('users',
    sa.Column('phone_number', sa.Text(), nullable=True),
    sa.Column('first_name', sa.Text(), nullable=True),
    sa.Column('whatsapp_name', sa.Text(), nullable=True),
    sa.Column('language', sa.Text(), nullable=False),
    sa.Column('is_guest', sa.Boolean(), nullable=False),
    sa.Column('guest_device_id', sa.Text(), nullable=True),
    sa.Column('registered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('guest_device_id', name=op.f('uq_users_guest_device_id')),
    sa.UniqueConstraint('phone_number', name=op.f('uq_users_phone_number'))
    )
    op.create_table('whatsapp_channels',
    sa.Column('phone_number_id', sa.Text(), nullable=False),
    sa.Column('display_number', sa.Text(), nullable=False),
    sa.Column('language', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_whatsapp_channels')),
    sa.UniqueConstraint('phone_number_id', name=op.f('uq_whatsapp_channels_phone_number_id'))
    )
    op.create_table('words',
    sa.Column('word_fr', sa.Text(), nullable=False),
    sa.Column('category', sa.Text(), nullable=False),
    sa.Column('is_core', sa.Boolean(), nullable=False),
    sa.Column('example_fr', sa.Text(), nullable=True),
    sa.Column('audio_fr_key', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_words')),
    sa.UniqueConstraint('word_fr', name=op.f('uq_words_word_fr'))
    )
    op.create_table('auth_sessions',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('refresh_token_hash', sa.Text(), nullable=False),
    sa.Column('platform', sa.Text(), nullable=False),
    sa.Column('device_name', sa.Text(), nullable=True),
    sa.Column('push_token', sa.Text(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_auth_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_sessions')),
    sa.UniqueConstraint('refresh_token_hash', name=op.f('uq_auth_sessions_refresh_token_hash'))
    )
    op.create_table('documents',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('source', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('failure_reason', sa.Text(), nullable=True),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('doc_type', sa.Text(), nullable=True),
    sa.Column('category', sa.Text(), nullable=False),
    sa.Column('issuer', sa.Text(), nullable=True),
    sa.Column('document_date', sa.Date(), nullable=True),
    sa.Column('urgency', sa.Text(), nullable=False),
    sa.Column('urgency_label', sa.Text(), nullable=True),
    sa.Column('main_due_date', sa.Date(), nullable=True),
    sa.Column('main_amount_xof', sa.Integer(), nullable=True),
    sa.Column('page_count', sa.Integer(), nullable=False),
    sa.Column('ocr_text', sa.Text(), nullable=True),
    sa.Column('summary_fr', sa.Text(), nullable=True),
    sa.Column('extracted_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_documents_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_documents'))
    )
    op.create_index('ix_documents_user_category', 'documents', ['user_id', 'category'], unique=False)
    op.create_index('ix_documents_user_created', 'documents', ['user_id', 'created_at'], unique=False)
    op.create_table('payments',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('plan_id', sa.UUID(), nullable=False),
    sa.Column('payer_phone', sa.Text(), nullable=True),
    sa.Column('amount_xof', sa.Integer(), nullable=False),
    sa.Column('provider', sa.Text(), nullable=False),
    sa.Column('method', sa.Text(), nullable=True),
    sa.Column('public_token', sa.Text(), nullable=False),
    sa.Column('provider_ref', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], name=op.f('fk_payments_plan_id_plans'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_payments_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payments')),
    sa.UniqueConstraint('public_token', name=op.f('uq_payments_public_token'))
    )
    op.create_table('practice_sessions',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('language', sa.Text(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('correct_count', sa.Integer(), nullable=False),
    sa.Column('total_count', sa.Integer(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_practice_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_practice_sessions'))
    )
    op.create_table('usage_counters',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('feature', sa.Text(), nullable=False),
    sa.Column('period', sa.Text(), nullable=False),
    sa.Column('count', sa.Integer(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_usage_counters_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_usage_counters')),
    sa.UniqueConstraint('user_id', 'feature', 'period', name=op.f('uq_usage_counters_user_id_feature_period'))
    )
    op.create_table('whatsapp_messages',
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('wa_phone', sa.Text(), nullable=False),
    sa.Column('channel_id', sa.UUID(), nullable=False),
    sa.Column('direction', sa.Text(), nullable=False),
    sa.Column('wa_message_id', sa.Text(), nullable=False),
    sa.Column('type', sa.Text(), nullable=False),
    sa.Column('template_name', sa.Text(), nullable=True),
    sa.Column('body_text', sa.Text(), nullable=True),
    sa.Column('wa_media_id', sa.Text(), nullable=True),
    sa.Column('media_key', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['channel_id'], ['whatsapp_channels.id'], name=op.f('fk_whatsapp_messages_channel_id_whatsapp_channels'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_whatsapp_messages_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_whatsapp_messages')),
    sa.UniqueConstraint('wa_message_id', name=op.f('uq_whatsapp_messages_wa_message_id'))
    )
    op.create_index('ix_whatsapp_messages_phone_created', 'whatsapp_messages', ['wa_phone', 'created_at'], unique=False)
    op.create_index('ix_whatsapp_messages_user_created', 'whatsapp_messages', ['user_id', 'created_at'], unique=False)
    op.create_table('word_translations',
    sa.Column('word_id', sa.UUID(), nullable=False),
    sa.Column('language', sa.Text(), nullable=False),
    sa.Column('meaning', sa.Text(), nullable=False),
    sa.Column('audio_key', sa.Text(), nullable=False),
    sa.Column('validated', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['word_id'], ['words.id'], name=op.f('fk_word_translations_word_id_words'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_word_translations')),
    sa.UniqueConstraint('word_id', 'language', name=op.f('uq_word_translations_word_id_language'))
    )
    op.create_table('conversations',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=True),
    sa.Column('source', sa.Text(), nullable=False),
    sa.Column('channel_id', sa.UUID(), nullable=True),
    sa.Column('language', sa.Text(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('context_summary', sa.Text(), nullable=True),
    sa.Column('last_message_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['channel_id'], ['whatsapp_channels.id'], name=op.f('fk_conversations_channel_id_whatsapp_channels'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_conversations_document_id_documents'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_conversations_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_conversations'))
    )
    op.create_index('ix_conversations_user_last_message', 'conversations', ['user_id', 'last_message_at'], unique=False)
    op.create_table('document_explanations',
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('language', sa.Text(), nullable=False),
    sa.Column('variant', sa.Text(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('text_fr', sa.Text(), nullable=False),
    sa.Column('audio_key', sa.Text(), nullable=False),
    sa.Column('audio_duration_s', sa.Integer(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_document_explanations_document_id_documents'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_explanations')),
    sa.UniqueConstraint('document_id', 'language', 'variant', name=op.f('uq_document_explanations_document_id_language_variant'))
    )
    op.create_table('document_files',
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('file_key', sa.Text(), nullable=False),
    sa.Column('mime_type', sa.Text(), nullable=False),
    sa.Column('original_filename', sa.Text(), nullable=True),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('ocr_text', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_document_files_document_id_documents'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_files'))
    )
    op.create_table('document_key_points',
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('language', sa.Text(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('tag', sa.Text(), nullable=False),
    sa.Column('title_fr', sa.Text(), nullable=False),
    sa.Column('detail_fr', sa.Text(), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('amount_xof', sa.Integer(), nullable=True),
    sa.Column('audio_key', sa.Text(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_document_key_points_document_id_documents'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_key_points')),
    sa.UniqueConstraint('document_id', 'language', 'position', name=op.f('uq_document_key_points_document_id_language_position'))
    )
    op.create_table('document_suggested_questions',
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('language', sa.Text(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('text_fr', sa.Text(), nullable=False),
    sa.Column('audio_key', sa.Text(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_document_suggested_questions_document_id_documents'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_suggested_questions')),
    sa.UniqueConstraint('document_id', 'language', 'position', name=op.f('uq_document_suggested_questions_document_id_language_position'))
    )
    op.create_table('document_words',
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('word_id', sa.UUID(), nullable=False),
    sa.Column('sentence_fr', sa.Text(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_document_words_document_id_documents'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['word_id'], ['words.id'], name=op.f('fk_document_words_word_id_words'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_words')),
    sa.UniqueConstraint('document_id', 'word_id', name=op.f('uq_document_words_document_id_word_id'))
    )
    op.create_table('practice_answers',
    sa.Column('session_id', sa.UUID(), nullable=False),
    sa.Column('word_id', sa.UUID(), nullable=False),
    sa.Column('chosen_word_id', sa.UUID(), nullable=False),
    sa.Column('is_correct', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['chosen_word_id'], ['words.id'], name=op.f('fk_practice_answers_chosen_word_id_words'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['session_id'], ['practice_sessions.id'], name=op.f('fk_practice_answers_session_id_practice_sessions'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['word_id'], ['words.id'], name=op.f('fk_practice_answers_word_id_words'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_practice_answers'))
    )
    op.create_table('prescription_lines',
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('page_position', sa.Integer(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('name_read', sa.Text(), nullable=True),
    sa.Column('lexicon_name', sa.Text(), nullable=True),
    sa.Column('lexicon_suggestion', sa.Text(), nullable=True),
    sa.Column('strength', sa.Text(), nullable=True),
    sa.Column('times_per_day', sa.Integer(), nullable=True),
    sa.Column('duration_days', sa.Integer(), nullable=True),
    sa.Column('timing', sa.Text(), nullable=True),
    sa.Column('field_statuses', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('pharmacology_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_prescription_lines_document_id_documents'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_prescription_lines')),
    sa.UniqueConstraint('document_id', 'position', name=op.f('uq_prescription_lines_document_id_position'))
    )
    op.create_table('subscriptions',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('plan_id', sa.UUID(), nullable=False),
    sa.Column('origin', sa.Text(), nullable=False),
    sa.Column('payment_id', sa.UUID(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('reminder_sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], name=op.f('fk_subscriptions_payment_id_payments')),
    sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], name=op.f('fk_subscriptions_plan_id_plans'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_subscriptions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_subscriptions')),
    sa.UniqueConstraint('payment_id', name=op.f('uq_subscriptions_payment_id'))
    )
    op.create_index('ix_subscriptions_user_expires', 'subscriptions', ['user_id', 'expires_at'], unique=False)
    op.create_table('user_words',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('word_id', sa.UUID(), nullable=False),
    sa.Column('source_document_id', sa.UUID(), nullable=True),
    sa.Column('correct_count', sa.Integer(), nullable=False),
    sa.Column('wrong_count', sa.Integer(), nullable=False),
    sa.Column('box', sa.Integer(), nullable=False),
    sa.Column('next_review_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('mastered', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['source_document_id'], ['documents.id'], name=op.f('fk_user_words_source_document_id_documents'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_words_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['word_id'], ['words.id'], name=op.f('fk_user_words_word_id_words'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_words')),
    sa.UniqueConstraint('user_id', 'word_id', name=op.f('uq_user_words_user_id_word_id'))
    )
    op.create_index('ix_user_words_user_next_review', 'user_words', ['user_id', 'next_review_at'], unique=False)
    op.create_table('conversation_documents',
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], name=op.f('fk_conversation_documents_conversation_id_conversations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_conversation_documents_document_id_documents'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_conversation_documents')),
    sa.UniqueConstraint('conversation_id', 'document_id', name=op.f('uq_conversation_documents_conversation_id_document_id'))
    )
    op.create_table('messages',
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.Text(), nullable=False),
    sa.Column('content_type', sa.Text(), nullable=False),
    sa.Column('language', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('text', sa.Text(), nullable=True),
    sa.Column('text_fr', sa.Text(), nullable=True),
    sa.Column('audio_key', sa.Text(), nullable=True),
    sa.Column('audio_duration_s', sa.Integer(), nullable=True),
    sa.Column('media_key', sa.Text(), nullable=True),
    sa.Column('source_quote', sa.Text(), nullable=True),
    sa.Column('explanation_id', sa.UUID(), nullable=True),
    sa.Column('suggested_question_id', sa.UUID(), nullable=True),
    sa.Column('whatsapp_message_id', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], name=op.f('fk_messages_conversation_id_conversations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['explanation_id'], ['document_explanations.id'], name=op.f('fk_messages_explanation_id_document_explanations'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['suggested_question_id'], ['document_suggested_questions.id'], name=op.f('fk_messages_suggested_question_id_document_suggested_questions'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['whatsapp_message_id'], ['whatsapp_messages.id'], name=op.f('fk_messages_whatsapp_message_id_whatsapp_messages'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_messages'))
    )
    op.create_index('ix_messages_conversation_created', 'messages', ['conversation_id', 'created_at'], unique=False)
    op.create_table('whatsapp_sessions',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('channel_id', sa.UUID(), nullable=False),
    sa.Column('state', sa.Text(), nullable=False),
    sa.Column('active_conversation_id', sa.UUID(), nullable=True),
    sa.Column('last_inbound_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['active_conversation_id'], ['conversations.id'], name=op.f('fk_whatsapp_sessions_active_conversation_id_conversations'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['channel_id'], ['whatsapp_channels.id'], name=op.f('fk_whatsapp_sessions_channel_id_whatsapp_channels'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_whatsapp_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_whatsapp_sessions')),
    sa.UniqueConstraint('user_id', 'channel_id', name=op.f('uq_whatsapp_sessions_user_id_channel_id'))
    )
    op.create_table('writings',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('type', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('current_step', sa.Integer(), nullable=False),
    sa.Column('total_steps', sa.Integer(), nullable=False),
    sa.Column('collected_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], name=op.f('fk_writings_conversation_id_conversations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_writings_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_writings')),
    sa.UniqueConstraint('conversation_id', name=op.f('uq_writings_conversation_id'))
    )
    op.create_table('ai_jobs',
    sa.Column('job_type', sa.Text(), nullable=False),
    sa.Column('provider', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('document_id', sa.UUID(), nullable=True),
    sa.Column('conversation_id', sa.UUID(), nullable=True),
    sa.Column('message_id', sa.UUID(), nullable=True),
    sa.Column('writing_id', sa.UUID(), nullable=True),
    sa.Column('input', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('cost_usd', sa.Numeric(precision=12, scale=6), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], name=op.f('fk_ai_jobs_conversation_id_conversations'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_ai_jobs_document_id_documents'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], name=op.f('fk_ai_jobs_message_id_messages'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_ai_jobs_user_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['writing_id'], ['writings.id'], name=op.f('fk_ai_jobs_writing_id_writings'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_jobs'))
    )
    op.create_index('ix_ai_jobs_status_created', 'ai_jobs', ['status', 'created_at'], unique=False)
    op.create_table('writing_outputs',
    sa.Column('writing_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('pdf_key', sa.Text(), nullable=False),
    sa.Column('readback_language', sa.Text(), nullable=False),
    sa.Column('readback_audio_key', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['writing_id'], ['writings.id'], name=op.f('fk_writing_outputs_writing_id_writings'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_writing_outputs')),
    sa.UniqueConstraint('writing_id', 'version', 'kind', name=op.f('uq_writing_outputs_writing_id_version_kind'))
    )
    op.create_table('writing_steps',
    sa.Column('writing_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('field_key', sa.Text(), nullable=False),
    sa.Column('question_message_id', sa.UUID(), nullable=False),
    sa.Column('answer_message_id', sa.UUID(), nullable=True),
    sa.Column('understood_value', sa.Text(), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['answer_message_id'], ['messages.id'], name=op.f('fk_writing_steps_answer_message_id_messages'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['question_message_id'], ['messages.id'], name=op.f('fk_writing_steps_question_message_id_messages'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['writing_id'], ['writings.id'], name=op.f('fk_writing_steps_writing_id_writings'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_writing_steps')),
    sa.UniqueConstraint('writing_id', 'position', name=op.f('uq_writing_steps_writing_id_position'))
    )


    op.execute(UPDATED_AT_FUNCTION)
    for table in _timestamped_tables():
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )
    plans = sa.table(
        "plans",
        sa.column("code", sa.Text()),
        sa.column("price_xof", sa.Integer()),
        sa.column("duration_days", sa.Integer()),
        sa.column("writings_per_month", sa.Integer()),
        sa.column("practice_per_day", sa.Integer()),
        sa.column("document_words", sa.Boolean()),
    )
    op.bulk_insert(
        plans,
        [
            dict(
                zip(
                    (
                        "code",
                        "price_xof",
                        "duration_days",
                        "writings_per_month",
                        "practice_per_day",
                        "document_words",
                    ),
                    plan,
                    strict=True,
                )
            )
            for plan in PLANS
        ],
    )


def downgrade() -> None:
    op.drop_table('writing_steps')
    op.drop_table('writing_outputs')
    op.drop_index('ix_ai_jobs_status_created', table_name='ai_jobs')
    op.drop_table('ai_jobs')
    op.drop_table('writings')
    op.drop_table('whatsapp_sessions')
    op.drop_index('ix_messages_conversation_created', table_name='messages')
    op.drop_table('messages')
    op.drop_table('conversation_documents')
    op.drop_index('ix_user_words_user_next_review', table_name='user_words')
    op.drop_table('user_words')
    op.drop_index('ix_subscriptions_user_expires', table_name='subscriptions')
    op.drop_table('subscriptions')
    op.drop_table('prescription_lines')
    op.drop_table('practice_answers')
    op.drop_table('document_words')
    op.drop_table('document_suggested_questions')
    op.drop_table('document_key_points')
    op.drop_table('document_files')
    op.drop_table('document_explanations')
    op.drop_index('ix_conversations_user_last_message', table_name='conversations')
    op.drop_table('conversations')
    op.drop_table('word_translations')
    op.drop_index('ix_whatsapp_messages_user_created', table_name='whatsapp_messages')
    op.drop_index('ix_whatsapp_messages_phone_created', table_name='whatsapp_messages')
    op.drop_table('whatsapp_messages')
    op.drop_table('usage_counters')
    op.drop_table('practice_sessions')
    op.drop_table('payments')
    op.drop_index('ix_documents_user_created', table_name='documents')
    op.drop_index('ix_documents_user_category', table_name='documents')
    op.drop_table('documents')
    op.drop_table('auth_sessions')
    op.drop_table('words')
    op.drop_table('whatsapp_channels')
    op.drop_table('users')
    op.drop_table('ui_prompts')
    op.drop_table('plans')
    op.drop_index('ix_otp_codes_phone_created', table_name='otp_codes')
    op.drop_table('otp_codes')
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
