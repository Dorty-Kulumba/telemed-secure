"""Create the original Telemed Secure tables.

Revision ID: 20261029_0001
Revises:
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261029_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "utilisateurs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nom", sa.String(length=100), nullable=False),
        sa.Column("prenom", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("telephone", sa.String(length=50), nullable=True),
        sa.Column("mot_de_passe_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("secret_mfa", sa.String(length=100), nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=True),
        sa.Column("date_creation", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_utilisateurs_id", "utilisateurs", ["id"], unique=False)
    op.create_index("ix_utilisateurs_email", "utilisateurs", ["email"], unique=True)

    op.create_table(
        "dossiers_medicaux",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("contenu_chiffre", sa.Text(), nullable=False),
        sa.Column("date_creation", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["utilisateurs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dossiers_medicaux_id", "dossiers_medicaux", ["id"], unique=False)

    op.create_table(
        "consentements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("medecin_id", sa.Integer(), nullable=False),
        sa.Column("statut", sa.Boolean(), nullable=True),
        sa.Column("date_creation", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("date_modification", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["medecin_id"], ["utilisateurs.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["utilisateurs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consentements_id", "consentements", ["id"], unique=False)

    op.create_table(
        "journal_audit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("utilisateur_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("ressource", sa.String(length=255), nullable=False),
        sa.Column("adresse_ip", sa.String(length=50), nullable=True),
        sa.Column("date_creation", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["utilisateur_id"], ["utilisateurs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_journal_audit_id", "journal_audit", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_journal_audit_id", table_name="journal_audit")
    op.drop_table("journal_audit")
    op.drop_index("ix_consentements_id", table_name="consentements")
    op.drop_table("consentements")
    op.drop_index("ix_dossiers_medicaux_id", table_name="dossiers_medicaux")
    op.drop_table("dossiers_medicaux")
    op.drop_index("ix_utilisateurs_email", table_name="utilisateurs")
    op.drop_index("ix_utilisateurs_id", table_name="utilisateurs")
    op.drop_table("utilisateurs")
