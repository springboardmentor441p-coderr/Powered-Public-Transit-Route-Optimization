"""${message}"""

from alembic import op
import sqlalchemy as sa
% if imports:
${imports}
% endif

def upgrade():
% if upgrade_ops:
${upgrade_ops}
% else:
    pass
% endif

def downgrade():
% if downgrade_ops:
${downgrade_ops}
% else:
    pass
% endif

