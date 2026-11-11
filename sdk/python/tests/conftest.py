from __future__ import annotations

import sys
from pathlib import Path

RAIZ_SDK = Path(__file__).resolve().parents[1]
if str(RAIZ_SDK) not in sys.path:
    sys.path.insert(0, str(RAIZ_SDK))
