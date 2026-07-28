from __future__ import annotations

import queue
import threading
from contextlib import contextmanager
from typing import Iterator

from modules.telemetry.application.dto import ExecutionEventDTO, TelemetrySummaryDTO, to_payload


class InMemoryExecutionRealtimePublisher:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, set[queue.Queue[dict]]] = {}

    @contextmanager
    def subscribe(self, execution_id: str) -> Iterator[queue.Queue[dict]]:
        subscription: queue.Queue[dict] = queue.Queue(maxsize=1000)
        with self._lock:
            self._subscribers.setdefault(execution_id, set()).add(subscription)
        try:
            yield subscription
        finally:
            with self._lock:
                subscribers = self._subscribers.get(execution_id)
                if subscribers is None:
                    return
                subscribers.discard(subscription)
                if not subscribers:
                    self._subscribers.pop(execution_id, None)

    def publish_execution_event(self, execution_id: str, event: ExecutionEventDTO) -> None:
        self._publish(execution_id, {"type": "execution.event", "event": to_payload(event)})

    def publish_execution_summary(self, summary: TelemetrySummaryDTO) -> None:
        self._publish(summary.execution_id, {"type": "execution.summary", "summary": to_payload(summary)})

    def _publish(self, execution_id: str, payload: dict) -> None:
        with self._lock:
            subscribers = list(self._subscribers.get(execution_id, set()))
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(payload)
            except queue.Full:
                try:
                    subscriber.get_nowait()
                    subscriber.put_nowait(payload)
                except queue.Empty:
                    pass


execution_realtime_publisher = InMemoryExecutionRealtimePublisher()
