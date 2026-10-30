"""docente que dio el aviso en ausencia

Revision ID: e50586914718
Revises: 7e9c500789c6
Create Date: 2026-10-30 00:29:04.131261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e50586914718'
down_revision: Union[str, Sequence[str], None] = '7e9c500789c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Primero nullable: los avisos que ya existen todavía no tienen docente
    op.add_column('ausencia', sa.Column('docente_id', sa.Integer(), nullable=True))
    # Los avisos existentes quedan a nombre del docente actual de su cátedra
    op.execute(
        "UPDATE ausencia SET docente_id = catedra.docente_id FROM catedra WHERE catedra.id = ausencia.catedra_id"
    )
    op.alter_column('ausencia', 'docente_id', existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(op.f('fk_ausencia_docente_id_docente'), 'ausencia', 'docente', ['docente_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f('fk_ausencia_docente_id_docente'), 'ausencia', type_='foreignkey')
    op.drop_column('ausencia', 'docente_id')
