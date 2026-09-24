"""Versioned response envelopes for the action interface."""
import time
import uuid
from kusto_query_cli.core.auth import get_timestamp
from kusto_query_cli.resources import load_version, load_protocol_version

WRAPPER_VERSION = load_version()
PROTOCOL_VERSION = load_protocol_version()


def create_envelope(action, status="success", data=None, error=None, start_time=None, authenticated=False, metadata_extra=None, request_id=None):
    """
    Wraps the response in a standard JSON envelope with metadata.

    Args:
        action (str): The name of the action being responded to.
        status (str): "success" or "error".
        data (dict, optional): The payload for successful responses.
        error (dict, optional): Error details (type, code, message, details).
        start_time (float, optional): Start time of the execution for performance tracking.
        authenticated (bool): Current authentication status.
        metadata_extra (dict, optional): Additional metadata to include.
        request_id (str, optional): Unique ID of the request being responded to.

    Returns:
        dict: The complete response envelope.
    """
    execution_time_ms = int((time.time() - start_time) * 1000) if start_time else 0

    metadata = {
        "timestamp": get_timestamp(),
        "execution_time_ms": execution_time_ms,
        "authenticated": authenticated,
        "wrapper_version": WRAPPER_VERSION,
        "protocol_version": PROTOCOL_VERSION,
    }
    # Always include a request_id to satisfy the response schema; generate one if not provided
    if request_id is None:
        try:
            request_id = str(uuid.uuid4())
        except Exception:
            request_id = "00000000-0000-0000-0000-000000000000"
    metadata["request_id"] = request_id
    if metadata_extra:
        try:
            metadata.update(metadata_extra)
        except Exception:
            pass

    response = {
        "status": status,
        "action": action,
        "data": data if data is not None else {},
        # Per response-envelope.schema.json, error must be either null or a valid error object
        # Use None (serialized as JSON null) when no error is provided
        "error": error if error is not None else None,
        "metadata": metadata,
    }
    return response
