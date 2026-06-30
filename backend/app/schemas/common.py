import sys

from app.platform import common_schemas as _common_schemas

sys.modules[__name__] = _common_schemas
