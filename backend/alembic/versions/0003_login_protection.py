"""Atomic login admission and one-use captcha redemption; no personal data changes."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_login_attempts_at", "login_attempts", ["at"])
    op.create_table("captcha_redemptions", sa.Column("token_hash", sa.String(64), primary_key=True),
                    sa.Column("expires_at", sa.DateTime(), nullable=False))
    op.create_index("ix_captcha_redemptions_expires_at", "captcha_redemptions", ["expires_at"])


def downgrade():
    op.drop_table("captcha_redemptions")
    op.drop_index("ix_login_attempts_at", table_name="login_attempts")
