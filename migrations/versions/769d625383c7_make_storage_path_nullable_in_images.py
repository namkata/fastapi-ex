"""Make storage_path nullable in images

Revision ID: 769d625383c7
Revises: bde3add3fcbb
Create Date: 2025-07-22 09:19:28.563477

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '769d625383c7'
down_revision = 'bde3add3fcbb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('images', 'file_size',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('images', 'file_type',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
    op.alter_column('images', 'width',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('images', 'height',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('images', 'description',
               existing_type=sa.TEXT(),
               nullable=True)
    op.alter_column('images', 'storage_type',
               existing_type=sa.VARCHAR(length=20),
               nullable=True)
    op.alter_column('images', 'storage_path',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
    op.alter_column('images', 'seaweedfs_fid',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
    op.alter_column('images', 's3_key',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
    op.alter_column('images', 's3_url',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('images', 's3_url',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.alter_column('images', 's3_key',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.alter_column('images', 'seaweedfs_fid',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.alter_column('images', 'storage_path',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.alter_column('images', 'storage_type',
               existing_type=sa.VARCHAR(length=20),
               nullable=False)
    op.alter_column('images', 'description',
               existing_type=sa.TEXT(),
               nullable=False)
    op.alter_column('images', 'height',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('images', 'width',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('images', 'file_type',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)
    op.alter_column('images', 'file_size',
               existing_type=sa.INTEGER(),
               nullable=False)
    # ### end Alembic commands ###
