from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_post_thumbnail"
down_revision: Union[str, None] = "0002_user_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "posts", sa.Column("thumbnail_url", sa.String(length=1024), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("posts", "thumbnail_url")
