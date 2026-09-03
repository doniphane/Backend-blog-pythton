from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_user_role"
down_revision: Union[str, None] = "0003_post_thumbnail"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), server_default="user", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
