def perform_http_request(payload: dict) -> dict:
    return {"executor": "http_request", "payload": payload}
