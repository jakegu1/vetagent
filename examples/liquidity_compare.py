"""Compare two saved successful liquidity response objects, before.json then after.json.

Save a REST /liquidity JSON body or MCP result.structuredContent, not an envelope.
Amounts are USD estimates. checked_at is reply time and source data may be cached.
"""

import json
import sys
from pathlib import Path

from assessment_policy import BYTE_CAP, _Parser, _emit, _nonfinite, _unique_object

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from liquidity_comparison import compare  # noqa: E402


def _read(path):
    with open(path, "rb") as handle:
        raw = handle.read(BYTE_CAP + 1)
    if len(raw) > BYTE_CAP:
        raise ValueError("input_too_large")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_nonfinite)


def main(argv=None):
    parser = _Parser(prog="liquidity_compare", description=__doc__, allow_abbrev=False)
    parser.add_argument("before", help="Earlier successful liquidity response object")
    parser.add_argument("after", help="Later successful liquidity response object")
    args = parser.parse_args(argv)
    try:
        result = compare(_read(args.before), _read(args.after))
    except (OSError, ValueError, UnicodeError, RecursionError, OverflowError):
        _emit({"error": "input_refused"})
        return 1
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
