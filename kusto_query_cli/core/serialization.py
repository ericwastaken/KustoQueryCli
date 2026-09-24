"""Shared conversion of ADX values to JSON-compatible values."""
import json

class KustoEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle types not supported by default,
    such as datetime objects and numpy types from pandas DataFrames.
    """


    def default(self, obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        # Handle pandas/numpy types if needed
        try:
            import numpy as np
            if isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
                return int(obj)
            if isinstance(obj, (np.float64, np.float32)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        return super().default(obj)


def _json_sanitize(value):
    """Best-effort conversion to JSON-serializable structures.

    Mirrors the approach used by the MCP STDIO server: convert pandas
    DataFrame/Series when available, handle numpy scalars/arrays, and
    datetime-like objects with isoformat. Falls back to string when needed.
    """
    # Fast path for primitives
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    # Datetime-like (duck-typing via isoformat)
    try:
        if hasattr(value, "isoformat"):
            return value.isoformat()
    except Exception:
        pass

    # pandas integration (optional)
    try:
        import pandas as pd  # type: ignore
    except Exception:
        pd = None  # type: ignore

    if pd is not None:
        try:
            if isinstance(value, pd.DataFrame):
                try:
                    # Convert to list of records and sanitize nested values
                    return [
                        {str(k): _json_sanitize(v) for k, v in row.items()}
                        for row in value.to_dict(orient="records")
                    ]
                except Exception:
                    # Fallback to JSON string if conversion fails
                    return json.loads(value.to_json(orient="records"))
            if isinstance(value, pd.Series):
                try:
                    return [_json_sanitize(v) for v in value.tolist()]
                except Exception:
                    try:
                        return {str(k): _json_sanitize(v) for k, v in value.to_dict().items()}
                    except Exception:
                        return str(value)
        except Exception:
            pass

    # NumPy scalars/arrays
    try:
        import numpy as np  # type: ignore
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return float(value)
        if isinstance(value, (np.ndarray,)):
            return [_json_sanitize(v) for v in value.tolist()]
    except Exception:
        pass

    # Bytes/bytearray → utf-8 or base64
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except Exception:
            import base64
            return base64.b64encode(bytes(value)).decode("ascii")

    # Sets/Tuples → lists
    if isinstance(value, (set, tuple)):
        return [_json_sanitize(v) for v in value]

    # Mappings → dict
    try:
        if isinstance(value, dict):
            return {str(k): _json_sanitize(v) for k, v in value.items()}
    except Exception:
        pass

    # Iterables (last resort) → list
    try:
        from collections.abc import Iterable
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
            return [_json_sanitize(v) for v in list(value)]
    except Exception:
        pass

    # Fallback to string
    try:
        return str(value)
    except Exception:
        return None
