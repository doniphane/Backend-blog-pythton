from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_user_profile"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("display_name", sa.String(length=100), nullable=True)
    )
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column(
        "users", sa.Column("avatar_url", sa.String(length=512), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "bio")
    op.drop_column("users", "display_name")
