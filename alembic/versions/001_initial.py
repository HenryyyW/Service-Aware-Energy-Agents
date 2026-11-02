"""Initial migration - create all tables.

Revision ID: 001
Revises: 
Create Date: 2026-11-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create experiments table
    op.create_table(
        'experiments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', sa.String(255), nullable=False),
        sa.Column('scenario_id', sa.String(255), nullable=False),
        sa.Column('controller_type', sa.String(50), nullable=False),
        sa.Column('controller_config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('random_seed', sa.Integer(), nullable=False, server_default='42'),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('grid_import_kwh', sa.Float(), nullable=True),
        sa.Column('grid_export_kwh', sa.Float(), nullable=True),
        sa.Column('peak_demand_kw', sa.Float(), nullable=True),
        sa.Column('load_factor', sa.Float(), nullable=True),
        sa.Column('pv_self_consumption_kwh', sa.Float(), nullable=True),
        sa.Column('pv_curtailment_kwh', sa.Float(), nullable=True),
        sa.Column('pv_generation_kwh', sa.Float(), nullable=True),
        sa.Column('battery_throughput_kwh', sa.Float(), nullable=True),
        sa.Column('battery_cycles', sa.Float(), nullable=True),
        sa.Column('carbon_emissions_kg', sa.Float(), nullable=True),
        sa.Column('comfort_score', sa.Float(), nullable=True),
        sa.Column('ev_charge_fulfillment', sa.Float(), nullable=True),
        sa.Column('flexible_load_fulfillment', sa.Float(), nullable=True),
        sa.Column('deadline_missed', sa.Integer(), nullable=True),
        sa.Column('voltage_violations', sa.Integer(), nullable=True),
        sa.Column('line_overloads', sa.Integer(), nullable=True),
        sa.Column('transformer_overloads', sa.Integer(), nullable=True),
        sa.Column('import_limit_violations', sa.Integer(), nullable=True),
        sa.Column('export_limit_violations', sa.Integer(), nullable=True),
        sa.Column('avg_voltage_pu', sa.Float(), nullable=True),
        sa.Column('max_line_loading_pct', sa.Float(), nullable=True),
        sa.Column('max_transformer_loading_pct', sa.Float(), nullable=True),
        sa.Column('nodal_power_balance_violations', sa.Integer(), nullable=True),
        sa.Column('agent_backend', sa.String(100), nullable=True),
        sa.Column('total_steps', sa.Integer(), nullable=True),
        sa.Column('fallback_steps', sa.Integer(), nullable=True),
        sa.Column('fallback_step_share', sa.Float(), nullable=True),
        sa.Column('kpis', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('per_member', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('diagnostic_reports', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('controller_config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('controller_code', sa.Text(), nullable=True),
        sa.Column('code_diffs', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('repair_iterations', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id'),
    )

    op.create_index('ix_experiments_status_created', 'experiments', ['status', 'created_at'])
    op.create_index('ix_experiments_scenario_controller', 'experiments', ['scenario_id', 'controller_type'])
    op.create_index('ix_experiments_run_id', 'experiments', ['run_id'], unique=True)

    # Create agent_tasks table
    op.create_table(
        'agent_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('input_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('output_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_agent_tasks_experiment_status', 'agent_tasks', ['experiment_id', 'status'])
    op.create_index('ix_agent_tasks_type_status', 'agent_tasks', ['task_type', 'status'])
    op.create_index('ix_agent_tasks_experiment_id', 'agent_tasks', ['experiment_id'])

    # Create simulation_runs table
    op.create_table(
        'simulation_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', sa.String(255), nullable=False),
        sa.Column('scenario_id', sa.String(255), nullable=False),
        sa.Column('controller', sa.String(100), nullable=False),
        sa.Column('regime', sa.String(50), nullable=False),
        sa.Column('seed', sa.Integer(), nullable=False, server_default='42'),
        sa.Column('config_hash', sa.String(64), nullable=False),
        sa.Column('config_snapshot', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('exit_code', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('output_dir', sa.String(512), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id'),
    )

    op.create_index('ix_simulation_runs_scenario_controller_regime', 'simulation_runs', ['scenario_id', 'controller', 'regime'])
    op.create_index('ix_simulation_runs_status_created', 'simulation_runs', ['status', 'created_at'])
    op.create_index('ix_simulation_runs_run_id', 'simulation_runs', ['run_id'], unique=True)

    # Create repair_sessions table
    op.create_table(
        'repair_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('max_iterations', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('current_iteration', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('final_report', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('total_time_seconds', sa.Float(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_repair_sessions_experiment_status', 'repair_sessions', ['experiment_id', 'status'])
    op.create_index('ix_repair_sessions_experiment_id', 'repair_sessions', ['experiment_id'])


def downgrade() -> None:
    op.drop_index('ix_repair_sessions_experiment_status', table_name='repair_sessions')
    op.drop_index('ix_repair_sessions_experiment_id', table_name='repair_sessions')
    op.drop_table('repair_sessions')

    op.drop_index('ix_simulation_runs_status_created', table_name='simulation_runs')
    op.drop_index('ix_simulation_runs_scenario_controller_regime', table_name='simulation_runs')
    op.drop_index('ix_simulation_runs_run_id', table_name='simulation_runs')
    op.drop_table('simulation_runs')

    op.drop_index('ix_agent_tasks_type_status', table_name='agent_tasks')
    op.drop_index('ix_agent_tasks_experiment_status', table_name='agent_tasks')
    op.drop_index('ix_agent_tasks_experiment_id', table_name='agent_tasks')
    op.drop_table('agent_tasks')

    op.drop_index('ix_experiments_scenario_controller', table_name='experiments')
    op.drop_index('ix_experiments_status_created', table_name='experiments')
    op.drop_index('ix_experiments_run_id', table_name='experiments')
    op.drop_table('experiments')