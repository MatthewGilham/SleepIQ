"""Health observations, import bookkeeping and rebuildable derived tables (Phase 2)."""

import sqlalchemy as sa
from alembic import op

revision = "0002_health"
down_revision = "0001_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("received_utc", sa.Integer(), nullable=False),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column("parser_version", sa.String(32), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=False),
        sa.CheckConstraint("length(sha256) = 64", name="ck_batch_digest"),
    )
    op.create_table(
        "observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("import_batches.id"), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("start_utc", sa.Integer(), nullable=False),
        sa.Column("end_utc", sa.Integer(), nullable=False),
        sa.Column("start_offset_min", sa.Integer(), nullable=False),
        sa.Column("end_offset_min", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(16)),
        sa.Column("qty", sa.Float()),
        sa.Column("avg", sa.Float()),
        sa.Column("min", sa.Float()),
        sa.Column("max", sa.Float()),
        sa.Column("has_heartbeat_series", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.CheckConstraint("end_utc >= start_utc", name="ck_obs_interval"),
        sa.CheckConstraint("status IN ('active', 'conflicting')", name="ck_obs_status"),
    )
    op.create_index("ix_obs_metric_time", "observations", ["metric", "status", "start_utc"])
    op.create_index("ix_obs_slot", "observations", ["metric", "source", "start_utc"])
    op.create_index("ix_obs_status_time", "observations", ["status", "start_utc"])
    op.create_table(
        "nightly_metrics",
        sa.Column("wake_date", sa.String(10), nullable=False),
        sa.Column("derivation_version", sa.String(32), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("session_start_utc", sa.Integer(), nullable=False),
        sa.Column("session_end_utc", sa.Integer(), nullable=False),
        sa.Column("start_offset_min", sa.Integer(), nullable=False),
        sa.Column("end_offset_min", sa.Integer(), nullable=False),
        sa.Column("onset_minute", sa.Float(), nullable=False),
        sa.Column("wake_minute", sa.Float(), nullable=False),
        sa.Column("asleep_s", sa.Integer(), nullable=False),
        sa.Column("core_s", sa.Integer(), nullable=False),
        sa.Column("deep_s", sa.Integer(), nullable=False),
        sa.Column("rem_s", sa.Integer(), nullable=False),
        sa.Column("awake_s", sa.Integer(), nullable=False),
        sa.Column("efficiency", sa.Float(), nullable=False),
        sa.Column("hr_mean", sa.Float()),
        sa.Column("hr_n", sa.Integer(), nullable=False),
        sa.Column("hr_method", sa.String(32)),
        sa.Column("hrv_mean", sa.Float()),
        sa.Column("hrv_n", sa.Integer(), nullable=False),
        sa.Column("resp_mean", sa.Float()),
        sa.Column("resp_n", sa.Integer(), nullable=False),
        sa.Column("rhr_mean", sa.Float()),
        sa.Column("rhr_n", sa.Integer(), nullable=False),
        sa.Column("temp_mean", sa.Float()),
        sa.Column("temp_n", sa.Integer(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("flags_json", sa.Text(), nullable=False),
        sa.Column("computed_utc", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("wake_date", "derivation_version"),
    )
    op.create_table(
        "general_metrics",
        sa.Column("local_date", sa.String(10), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("derivation_version", sa.String(32), nullable=False),
        sa.Column("mean", sa.Float(), nullable=False),
        sa.Column("n", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("local_date", "metric", "derivation_version"),
    )
    op.create_table(
        "nightly_scores",
        sa.Column("wake_date", sa.String(10), nullable=False),
        sa.Column("score_version", sa.String(32), nullable=False),
        sa.Column("derivation_version", sa.String(32), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("overall", sa.Float()),
        sa.Column("consistency", sa.Float()),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("computed_utc", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("wake_date", "score_version"),
        sa.CheckConstraint("status IN ('scored', 'insufficient_data')", name="ck_score_status"),
    )


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade is not supported; use an approved isolated restore")
