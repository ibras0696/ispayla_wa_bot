from __future__ import annotations

import sys
from pathlib import Path

# Всегда добавляем корень репозитория в PYTHONPATH, чтобы `import app`
# работал независимо от того, из какого интерпретатора запускают pytest.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
