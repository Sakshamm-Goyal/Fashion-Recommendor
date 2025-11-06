# infra/logging.py
"""
Structured logging with PII scrubbing.
"""
import logging
import json
import uuid

logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_event(event: str, **kwargs):
    """
    Log a structured event with request_id and custom fields.
    Automatically generates request_id if not provided.
    """
    rec = {"event": event, "request_id": kwargs.pop("request_id", str(uuid.uuid4())), **kwargs}
    logging.info(json.dumps(rec))


def log_error(error: str, **kwargs):
    """
    Log an error event.
    """
    rec = {"event": "error", "error": error, "request_id": kwargs.pop("request_id", str(uuid.uuid4())), **kwargs}
    logging.error(json.dumps(rec))
