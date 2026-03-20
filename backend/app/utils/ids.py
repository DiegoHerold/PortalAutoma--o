from uuid import uuid4


def generate_slug_suffix() -> str:
    return uuid4().hex[:8]
