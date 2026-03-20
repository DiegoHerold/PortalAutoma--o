import json
from typing import Any


def to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, default=str)
