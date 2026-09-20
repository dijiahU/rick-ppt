"""Decode model output envelopes without repairing or choosing report contents."""
import json
import re


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate key in structured output')
        value[key] = item
    return value


def _invalid_constant(value):
    raise ValueError('Non-JSON constant in structured output')


_DECODER = json.JSONDecoder(object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
_FENCE = re.compile(r'^\s*```json[ \t]*\r?\n(.*?)^[ \t]*```[ \t]*(?:\r?\n|$)',
                    re.MULTILINE | re.DOTALL | re.IGNORECASE)
_JSON_START = re.compile(r'(?<!\w)(?:["\-\d]|true\b|false\b|null\b|NaN\b|Infinity\b)')


def _check_prose(text):
    # Conservatively reject other payloads, including incomplete JSON containers.
    if any(marker in text for marker in ('```', '~~~', '{', '}', '[', ']')):
        raise ValueError('Ambiguous structured output envelope')
    for match in _JSON_START.finditer(text):
        try:
            _, end = _DECODER.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if end == len(text) or not (text[end].isalnum() or text[end] == '_'):
            raise ValueError('JSON value outside structured output fence')


def parse_structured_output(text):
    """Return one JSON object, either bare or in one explicit ```json fence.

    Surrounding prose must contain no other fences, JSON containers or standalone
    JSON value tokens. Duplicate keys, non-JSON constants and malformed payloads
    fail closed. This only decodes the envelope: callers must still perform their
    schema and semantic validation (for reviews, validate_report(value, pages)).
    The function is also usable on saved, completed agent messages for recovery.
    """
    if not isinstance(text, str):
        raise ValueError('Structured output must be text')
    text = text.strip()
    try:
        value = _DECODER.decode(text)
    except json.JSONDecodeError:
        matches = list(_FENCE.finditer(text))
        if len(matches) != 1:
            raise ValueError('Expected JSON or exactly one JSON fence') from None
        match = matches[0]
        _check_prose(text[:match.start()])
        _check_prose(text[match.end():])
        value = _DECODER.decode(match[1].strip())
    if not isinstance(value, dict):
        raise ValueError('Structured output must be a JSON object')
    return value
