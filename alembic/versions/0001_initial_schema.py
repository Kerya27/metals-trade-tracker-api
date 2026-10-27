"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        _ts(),
        sa.CheckConstraint("role IN ('admin', 'trader')", name="ck_users_role"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("contact_email", sa.String(320), nullable=False),
    )
    op.create_index("ix_suppliers_name", "suppliers", ["name"])

    op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "supplier_id",
            sa.Integer(),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("material", sa.String(100), nullable=False),
        sa.Column("quantity_tonnes", sa.Numeric(12, 3), nullable=False),
        sa.Column("price_per_tonne", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(20), nullable=False),
        sa.Column("incoterm", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        _ts(),
        sa.CheckConstraint("quantity_tonnes > 0", name="ck_offers_quantity_positive"),
        sa.CheckConstraint("price_per_tonne > 0", name="ck_offers_price_positive"),
        sa.CheckConstraint("currency IN ('EUR', 'USD', 'CZK')", name="ck_offers_currency"),
        sa.CheckConstraint("status IN ('ACTIVE', 'CLOSED')", name="ck_offers_status"),
    )
    op.create_index("ix_offers_supplier_id", "offers", ["supplier_id"])
    op.create_index("ix_offers_material", "offers", ["material"])
    op.create_index("ix_offers_status", "offers", ["status"])

    deal_statuses = "('DRAFT', 'NEGOTIATION', 'CONTRACTED', 'SHIPPED', 'CLOSED', 'CANCELLED')"
    op.create_table(
        "deals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "offer_id", sa.Integer(), sa.ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("buyer_name", sa.String(200), nullable=False),
        sa.Column("agreed_price_per_tonne", sa.Numeric(14, 2), nullable=False),
        sa.Column("quantity_tonnes", sa.Numeric(12, 3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        _ts(),
        sa.CheckConstraint("quantity_tonnes > 0", name="ck_deals_quantity_positive"),
        sa.CheckConstraint("agreed_price_per_tonne > 0", name="ck_deals_price_positive"),
        sa.CheckConstraint(f"status IN {deal_statuses}", name="ck_deals_status"),
    )
    op.create_index("ix_deals_offer_id", "deals", ["offer_id"])
    op.create_index("ix_deals_status", "deals", ["status"])
    op.create_index("ix_deals_created_by", "deals", ["created_by"])

    op.create_table(
        "deal_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "deal_id", sa.Integer(), sa.ForeignKey("deals.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column(
            "changed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("comment", sa.Text(), nullable=True),
    )
    op.create_index("ix_deal_status_history_deal_id", "deal_status_history", ["deal_id"])

    # Enforce append-only history at the database level.
    op.execute(
        """
        CREATE FUNCTION deal_status_history_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'deal_status_history is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_deal_status_history_immutable
        BEFORE UPDATE OR DELETE ON deal_status_history
        FOR EACH ROW EXECUTE FUNCTION deal_status_history_immutable();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_deal_status_history_immutable ON deal_status_history"
    )
    op.execute("DROP FUNCTION IF EXISTS deal_status_history_immutable()")
    op.drop_table("deal_status_history")
    op.drop_table("deals")
    op.drop_table("offers")
    op.drop_table("suppliers")
    op.drop_table("users")
