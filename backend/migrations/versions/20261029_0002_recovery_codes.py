"""Add forced password change and single-use MFA recovery codes.

Revision ID: 20261029_0002
Revises: 20261029_0001
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261029_0002"
down_revision: Union[str, None] = "20261029_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "utilisateurs",
        sa.Column("mot_de_passe_a_changer", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("utilisateurs", sa.Column("token_version", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.create_table(
        "codes_recuperation_mfa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("utilisateur_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("date_creation", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("utilise_le", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["utilisateur_id"], ["utilisateurs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_codes_recuperation_mfa_id", "codes_recuperation_mfa", ["id"], unique=False)
    op.create_index(
        "ix_codes_recuperation_mfa_utilisateur_id",
        "codes_recuperation_mfa",
        ["utilisateur_id"],
        unique=False,
    )
    op.create_index(
        "ix_codes_recuperation_mfa_code_hash",
        "codes_recuperation_mfa",
        ["code_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_codes_recuperation_mfa_code_hash", table_name="codes_recuperation_mfa")
    op.drop_index("ix_codes_recuperation_mfa_utilisateur_id", table_name="codes_recuperation_mfa")
    op.drop_index("ix_codes_recuperation_mfa_id", table_name="codes_recuperation_mfa")
    op.drop_table("codes_recuperation_mfa")
    op.drop_column("utilisateurs", "token_version")
    op.drop_column("utilisateurs", "mot_de_passe_a_changer")
