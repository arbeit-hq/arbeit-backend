"""add quality_score and update user preferences

Revision ID: 003_quality_prefs
Revises: 002_enhance_job_schema
Create Date: 2025-10-08 17:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_quality_prefs'
down_revision = '002_enhance_job_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add quality_score to jobs table
    op.add_column('jobs', sa.Column('quality_score', sa.Float(), nullable=True))
    op.create_index('ix_jobs_quality_score', 'jobs', ['quality_score'], unique=False)
    
    # Update user_preferences table
    # Add new columns
    op.add_column('user_preferences', sa.Column('excluded_keywords', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('user_preferences', sa.Column('job_types', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('user_preferences', sa.Column('notification_frequency', sa.String(length=50), nullable=False, server_default='daily'))
    
    # Add unique constraint on user_id (if it doesn't exist)
    op.create_unique_constraint('uq_user_preferences_user_id', 'user_preferences', ['user_id'])


def downgrade() -> None:
    # Remove quality_score from jobs
    op.drop_index('ix_jobs_quality_score', table_name='jobs')
    op.drop_column('jobs', 'quality_score')
    
    # Remove new columns from user_preferences
    op.drop_constraint('uq_user_preferences_user_id', 'user_preferences', type_='unique')
    op.drop_column('user_preferences', 'notification_frequency')
    op.drop_column('user_preferences', 'job_types')
    op.drop_column('user_preferences', 'excluded_keywords')