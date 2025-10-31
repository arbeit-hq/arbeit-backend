"""Enhance job schema with additional fields

Revision ID: 002_enhance_job_schema
Revises: 001_initial_tables
Create Date: 2025-10-01 20:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_enhance_job_schema'
down_revision = '001_initial_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing fields to job_sources table
    op.add_column('job_sources', sa.Column('priority', sa.Integer(), nullable=False, server_default='5'))
    op.add_column('job_sources', sa.Column('last_scraped_at', sa.DateTime(), nullable=True))
    op.add_column('job_sources', sa.Column('scrape_frequency', sa.Integer(), nullable=False, server_default='7200'))
    op.add_column('job_sources', sa.Column('total_jobs_found', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('job_sources', sa.Column('total_errors', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('job_sources', sa.Column('success_rate', sa.Float(), nullable=True))
    
    # Update source_type to use enum
    op.execute("ALTER TABLE job_sources ALTER COLUMN source_type TYPE VARCHAR(50)")
    
    # Add missing fields to jobs table
    op.add_column('jobs', sa.Column('remote_work', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('jobs', sa.Column('job_type', sa.String(length=100), nullable=True))
    op.add_column('jobs', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('jobs', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')))
    
    # Create job_metadata table
    op.create_table('job_metadata',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_unique_constraint('uq_job_metadata_job_key', 'job_metadata', ['job_id', 'key'])
    op.create_index('ix_job_metadata_job_key', 'job_metadata', ['job_id', 'key'])
    
    # Create scraper_logs table
    op.create_table('scraper_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('level', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['job_sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scraper_logs_created_at', 'scraper_logs', ['created_at'])
    op.create_index('ix_scraper_logs_source_created', 'scraper_logs', ['source_id', 'created_at'])
    op.create_index('ix_scraper_logs_level_created', 'scraper_logs', ['level', 'created_at'])
    
    # Add composite indexes for jobs table
    op.create_index('ix_jobs_source_posted', 'jobs', ['source_id', 'posted_at'])
    op.create_index('ix_jobs_active_created', 'jobs', ['is_active', 'created_at'])
    op.create_index('ix_jobs_title_company', 'jobs', ['title', 'company'])
    
    # Add unique constraint on job_sources name
    op.create_unique_constraint('uq_job_sources_name', 'job_sources', ['name'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_jobs_title_company', table_name='jobs')
    op.drop_index('ix_jobs_active_created', table_name='jobs')
    op.drop_index('ix_jobs_source_posted', table_name='jobs')
    
    # Drop scraper_logs table
    op.drop_index('ix_scraper_logs_level_created', table_name='scraper_logs')
    op.drop_index('ix_scraper_logs_source_created', table_name='scraper_logs')
    op.drop_index('ix_scraper_logs_created_at', table_name='scraper_logs')
    op.drop_table('scraper_logs')
    
    # Drop job_metadata table
    op.drop_index('ix_job_metadata_job_key', table_name='job_metadata')
    op.drop_table('job_metadata')
    op.drop_constraint('uq_job_metadata_job_key', 'job_metadata', type_='unique')
    
    # Remove added columns from jobs
    op.drop_column('jobs', 'updated_at')
    op.drop_column('jobs', 'is_active')
    op.drop_column('jobs', 'job_type')
    op.drop_column('jobs', 'remote_work')
    
    # Remove added columns from job_sources
    op.drop_constraint('uq_job_sources_name', 'job_sources', type_='unique')
    op.drop_column('job_sources', 'success_rate')
    op.drop_column('job_sources', 'total_errors')
    op.drop_column('job_sources', 'total_jobs_found')
    op.drop_column('job_sources', 'scrape_frequency')
    op.drop_column('job_sources', 'last_scraped_at')
    op.drop_column('job_sources', 'priority')