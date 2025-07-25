"""Add default to updated_at in users

Revision ID: 0db2e8dd572e
Revises: af6486c812f1
Create Date: 2025-07-22 08:14:20.264003

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0db2e8dd572e'
down_revision = 'af6486c812f1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('users', 'updated_at',
               existing_type=sa.TIMESTAMP(timezone=True),
               server_default=sa.text('now()'),
               existing_nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('users', 'updated_at',
               existing_type=sa.TIMESTAMP(timezone=True),
               server_default=None,
               existing_nullable=False)
    # ### end Alembic commands ###
