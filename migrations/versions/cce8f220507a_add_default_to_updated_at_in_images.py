"""add_default_to_updated_at_in_images

Revision ID: cce8f220507a
Revises: bd2238adf3cb
Create Date: 2025-07-22 09:32:15.801702

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cce8f220507a'
down_revision = 'bd2238adf3cb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('images', 'updated_at',
               existing_type=sa.DateTime(timezone=True),
               server_default=sa.text('now()'))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('images', 'updated_at',
               existing_type=sa.DateTime(timezone=True),
               server_default=None)
    # ### end Alembic commands ###
