"""Configurable per-IP/account escalation and unknown-name bans."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET, JSONB
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("login_protection_settings", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("policy", JSONB(), nullable=False))
    op.create_table("login_bans", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("ip", INET(), nullable=False), sa.Column("username", sa.String(64), nullable=False),
                    sa.Column("failures", sa.Integer(), nullable=False), sa.Column("stage", sa.Integer(), nullable=False),
                    sa.Column("banned_until", sa.DateTime()), sa.Column("updated_at", sa.DateTime(), nullable=False),
                    sa.Column("reason", sa.String(32), nullable=False),
                    sa.UniqueConstraint("ip", "username", name="uq_login_bans_identity"))


def downgrade():
    op.drop_table("login_bans")
    op.drop_table("login_protection_settings")
