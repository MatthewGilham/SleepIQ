"""Nullable weighted-HR provenance; existing measurements and active versions are untouched."""

import sqlalchemy as sa
from alembic import op

revision = "0003_weighted_hr"
down_revision = "0002_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("hr_eligible_n", "hr_contributing_n", "hr_covered_s", "hr_window_s"):
        minimum = 1 if name == "hr_window_s" else 0
        op.add_column(
            "nightly_metrics",
            sa.Column(
                name, sa.Integer(), sa.CheckConstraint(f"{name} >= {minimum}"), nullable=True
            ),
        )
    op.add_column(
        "nightly_metrics",
        sa.Column(
            "hr_coverage",
            sa.Float(),
            sa.CheckConstraint("hr_coverage BETWEEN 0 AND 1"),
            nullable=True,
        ),
    )
    op.add_column("nightly_metrics", sa.Column("hr_fallback_reason", sa.String(32), nullable=True))
    op.add_column(
        "nightly_metrics",
        sa.Column(
            "derivation_config_hash",
            sa.String(64),
            sa.CheckConstraint("length(derivation_config_hash) = 64"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade is not supported; use an approved isolated restore")
