"""Non-secret settings foundation; health-observation schema is a later increment."""

import sqlalchemy as sa
from alembic import op

revision = "0001_settings"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(128), primary_key=True, nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.CheckConstraint("length(key) BETWEEN 1 AND 128", name="ck_settings_key_length"),
    )


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade is not supported; use an approved isolated restore")
