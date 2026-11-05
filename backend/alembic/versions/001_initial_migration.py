"""Initial migration - create all tables

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', sa.Enum('admin', 'operator', 'viewer', name='userrole'), default='viewer', nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_superuser', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('token', sa.String(512), unique=True, nullable=False, index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.text('now()'), nullable=False),
        sa.Column('revoked', sa.Boolean(), default=False, nullable=False),
    )
    op.create_index('ix_refresh_tokens_user_expires', 'refresh_tokens', ['user_id', 'expires_at'])

    # Create lines table
    op.create_table(
        'lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('code', sa.String(10), unique=True, nullable=False, index=True),
        sa.Column('color', sa.String(7), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )

    # Create stations table
    op.create_table(
        'stations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('line_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('lines.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('code', sa.String(10), unique=True, nullable=False, index=True),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('capacity', sa.Integer(), default=1000, nullable=False),
        sa.Column('zone', sa.String(50), nullable=True),
        sa.Column('is_interchange', sa.Boolean(), default=False, nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )
    op.create_unique_constraint('uq_line_order', 'stations', ['line_id', 'order'])
    op.create_index('ix_stations_location', 'stations', ['latitude', 'longitude'])

    # Create trains table
    op.create_table(
        'trains',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('train_number', sa.String(20), unique=True, nullable=False, index=True),
        sa.Column('line_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('lines.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('capacity', sa.Integer(), default=500, nullable=False),
        sa.Column('status', sa.Enum('active', 'inactive', 'maintenance', 'delayed', name='trainstatus'), default='active', nullable=False),
        sa.Column('current_station_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('stations.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )

    # Create schedules table
    op.create_table(
        'schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('train_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trains.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('station_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('stations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('arrival_time', sa.Time(), nullable=True),
        sa.Column('departure_time', sa.Time(), nullable=True),
        sa.Column('day_type', sa.Enum('weekday', 'saturday', 'sunday', 'holiday', name='daytype'), default='weekday', nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )
    op.create_unique_constraint('uq_train_station_day', 'schedules', ['train_id', 'station_id', 'day_type'])
    op.create_index('ix_schedules_train_sequence', 'schedules', ['train_id', 'sequence'])

    # Create ridership_records table
    op.create_table(
        'ridership_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('station_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('stations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('entry_count', sa.Integer(), default=0, nullable=False),
        sa.Column('exit_count', sa.Integer(), default=0, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('source', sa.Enum('smart_card', 'ticketing', 'sensor', 'manual', 'estimated', name='datasource'), default='estimated', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_ridership_station_timestamp', 'ridership_records', ['station_id', 'timestamp'])
    op.create_index('ix_ridership_timestamp_source', 'ridership_records', ['timestamp', 'source'])

    # Create train_occupancy table
    op.create_table(
        'train_occupancy',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('train_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trains.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('station_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('stations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('occupancy_count', sa.Integer(), default=0, nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_occupancy_train_timestamp', 'train_occupancy', ['train_id', 'timestamp'])
    op.create_index('ix_occupancy_station_timestamp', 'train_occupancy', ['station_id', 'timestamp'])

    # Create congestion_events table
    op.create_table(
        'congestion_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('station_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('stations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('severity', sa.Enum('low', 'medium', 'high', 'critical', name='congestionseverity'), nullable=False),
        sa.Column('predicted', sa.Boolean(), default=False, nullable=False),
        sa.Column('passenger_count', sa.Integer(), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_congestion_station_timestamp', 'congestion_events', ['station_id', 'timestamp'])
    op.create_index('ix_congestion_severity_timestamp', 'congestion_events', ['severity', 'timestamp'])

    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('type', sa.Enum('overcrowding', 'delay', 'emergency', 'maintenance', 'schedule_change', 'system', name='alerttype'), nullable=False, index=True),
        sa.Column('severity', sa.Enum('info', 'warning', 'critical', name='alertseverity'), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('station_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('stations.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('train_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('trains.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('is_read', sa.Boolean(), default=False, nullable=False),
        sa.Column('is_dismissed', sa.Boolean(), default=False, nullable=False),
        sa.Column('dismissed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.text('now()'), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_alerts_type_severity', 'alerts', ['type', 'severity'])
    op.create_index('ix_alerts_station_created', 'alerts', ['station_id', 'created_at'])
    op.create_index('ix_alerts_active', 'alerts', ['is_read', 'is_dismissed', 'expires_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('alerts')
    op.drop_table('congestion_events')
    op.drop_table('train_occupancy')
    op.drop_table('ridership_records')
    op.drop_table('schedules')
    op.drop_table('trains')
    op.drop_table('stations')
    op.drop_table('lines')
    op.drop_table('refresh_tokens')
    op.drop_table('users')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS userrole')
    op.execute('DROP TYPE IF EXISTS trainstatus')
    op.execute('DROP TYPE IF EXISTS daytype')
    op.execute('DROP TYPE IF EXISTS datasource')
    op.execute('DROP TYPE IF EXISTS congestionseverity')
    op.execute('DROP TYPE IF EXISTS alerttype')
    op.execute('DROP TYPE IF EXISTS alertseverity')