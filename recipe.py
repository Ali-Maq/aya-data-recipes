"""Saved JSON export recipes for Open WebUI.

Implements export_recipe(payload) that turns JSON records + column path
definitions into (columns, rows, csv), matching jq's getpath traversal and
@csv serialization semantics.

Allowed imports: json, csv, io, math, typing, collections, re (stdlib only).
"""

import json

MAX_ROWS = 10000
MAX_COLUMNS = 32
MAX_LABEL_LEN = 128
MAX_PATH_SEGMENTS = 16
MAX_SAFE_INT = 9007199254740991
LIMIT_BYTES = 1048576


def export_recipe(payload):
    """Export records per the declared column/path recipe.

    Returns a success dict {"columns": [...], "rows": [[...]], "csv": "..."}
    or an error dict {"error": CODE}.
    """
    if not isinstance(payload, dict):
        return {"error": "invalid_recipe"}

    if "records" not in payload:
        return {"error": "invalid_recipe"}
    if "columns" not in payload:
        return {"error": "invalid_recipe"}

    records = payload["records"]
    columns = payload["columns"]

    if not isinstance(records, list):
        return {"error": "invalid_recipe"}
    if not isinstance(columns, list):
        return {"error": "invalid_recipe"}

    # Row/column bounds checked up front.
    if len(records) > MAX_ROWS:
        return {"error": "limit_exceeded"}
    if len(columns) > MAX_COLUMNS:
        return {"error": "limit_exceeded"}

    # Validate column definitions.
    for col in columns:
        if not isinstance(col, dict):
            return {"error": "invalid_recipe"}
        if "label" not in col:
            return {"error": "invalid_recipe"}
        if "path" not in col:
            return {"error": "invalid_recipe"}

        label = col["label"]
        path = col["path"]

        if not isinstance(label, str):
            return {"error": "invalid_recipe"}
        if len(label) == 0 or len(label) > MAX_LABEL_LEN:
            return {"error": "invalid_recipe"}

        if not isinstance(path, list):
            return {"error": "invalid_recipe"}
        if len(path) > MAX_PATH_SEGMENTS:
            return {"error": "invalid_recipe"}
        for segment in path:
            if isinstance(segment, bool):
                return {"error": "invalid_recipe"}
            if not isinstance(segment, (str, int)):
                return {"error": "invalid_recipe"}
            if isinstance(segment, int):
                if segment < 0:
                    return {"error": "invalid_recipe"}
                if segment > MAX_SAFE_INT:
                    return {"error": "unsupported_number"}

        # Validate fallback options.
        if "fallback_mode" in col:
            mode = col["fallback_mode"]
            if mode not in ("jq", "null"):
                return {"error": "invalid_recipe"}
        if "fallback" in col:
            fallback = col["fallback"]
            if _contains_unsupported_number(fallback):
                return {"error": "unsupported_number"}
            if not _is_scalar(fallback):
                return {"error": "non_scalar"}

    # Scan the full request for unsupported numbers ("anywhere in the
    # request") and non-scalar issues, guarding against pathological depth.
    try:
        if _contains_unsupported_number(payload):
            return {"error": "unsupported_number"}

        encoded_size = _encoded_size(payload)
    except RecursionError:
        return {"error": "limit_exceeded"}

    if encoded_size > LIMIT_BYTES:
        return {"error": "limit_exceeded"}

    # Columns are "1..32 objects" per the contract; empty is a malformed shape.
    # Checked after the value-level number scan so a prohibited number (e.g. in
    # an unrelated field) is still reported as unsupported_number.
    if len(columns) == 0:
        return {"error": "invalid_recipe"}

    labels = [col["label"] for col in columns]
    rows = []

    for record in records:
        # Records must be JSON objects or arrays; a bare (non-null) scalar
        # record is a malformed request, distinct from traversal errors.
        if record is not None and not isinstance(record, (dict, list)):
            return {"error": "invalid_recipe"}

        row = []
        for col in columns:
            value = _traverse(record, col["path"])
            # Detect path_type mismatch during traversal (returned as sentinel).
            if value is _PATH_TYPE:
                return {"error": "path_type"}

            has_fallback_key = "fallback" in col
            fallback = col.get("fallback", None)
            mode = col.get("fallback_mode", "jq")

            if has_fallback_key and _needs_fallback(value, mode):
                value = fallback

            # A bare non-scalar result (object/array) cannot be csv-formatted.
            if not _is_scalar(value):
                return {"error": "non_scalar"}

            row.append(value)
        rows.append(row)

    csv = _to_csv(labels, rows)
    return {"columns": labels, "rows": rows, "csv": csv}


_PATH_TYPE = object()


def _traverse(record, path):
    value = record
    for segment in path:
        if value is None:
            return None
        if isinstance(value, dict):
            if isinstance(segment, str):
                if segment in value:
                    value = value[segment]
                else:
                    return None
            else:
                return _PATH_TYPE  # Cannot index object with number
        elif isinstance(value, list):
            if isinstance(segment, int):
                if 0 <= segment < len(value):
                    value = value[segment]
                else:
                    return None
            else:
                return _PATH_TYPE  # Cannot index array with string
        else:
            # Null traversal returns null (contract), but indexing any other
            # scalar (string/number/bool) is an incompatible traversal that
            # jq rejects ("Cannot index <type> with ...").
            return _PATH_TYPE
    return value


def _is_scalar(value):
    return value is None or isinstance(value, (str, bool, int))


def _needs_fallback(value, mode):
    if mode == "null":
        return value is None
    # jq mode: replace null, missing, or false
    return value is None or value is False


def _contains_unsupported_number(obj):
    if isinstance(obj, bool):
        return False
    if isinstance(obj, int):
        return not (-MAX_SAFE_INT <= obj <= MAX_SAFE_INT)
    if isinstance(obj, float):
        return True
    if isinstance(obj, str):
        return False
    if isinstance(obj, list):
        return any(_contains_unsupported_number(item) for item in obj)
    if isinstance(obj, dict):
        return any(
            _contains_unsupported_number(k) or _contains_unsupported_number(v)
            for k, v in obj.items()
        )
    return False


def _encoded_size(obj):
    try:
        encoded = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8")
        return len(encoded)
    except (ValueError, TypeError):
        return LIMIT_BYTES + 1


def _to_csv(labels, rows):
    lines = []

    def encode_cell(value):
        if value is None:
            return ""
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, str):
            escaped = value.replace("\x00", "\\0")
            return '"' + escaped.replace('"', '""') + '"'
        return ""

    lines.append(",".join(encode_cell(l) for l in labels))
    for row in rows:
        lines.append(",".join(encode_cell(c) for c in row))
    return "\n".join(lines) + "\n"