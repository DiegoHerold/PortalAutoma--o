def resolve_executor_queue(executor_type: str, priority: str) -> str:
    return priority if executor_type else "normal"
