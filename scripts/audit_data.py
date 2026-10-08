"""Audit a local opportunity snapshot without connecting to a database."""

import argparse
import json
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo


SEOUL = ZoneInfo("Asia/Seoul")
DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "data/moabom_opportunities_v2.json"


def audit(path: Path, as_of: date) -> dict:
    rows = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list):
        raise ValueError("The input must be a JSON array.")

    def category(row):
        value = row.get("category")
        return value.get("code") if isinstance(value, dict) else value

    def expired(row):
        value = (row.get("dates") or {}).get("recruit_end_at")
        if not value:
            return False
        try:
            end = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return False
        # Date-only deadlines are interpreted as the end of that Seoul day.
        if len(value) == 10:
            end = datetime.combine(end.date(), time.max, tzinfo=SEOUL)
        elif end.tzinfo is None:
            end = end.replace(tzinfo=SEOUL)
        return end < datetime.combine(as_of, time.min, tzinfo=SEOUL)

    field_names = [
        "id", "title", "source", "source_url", "summary", "thumbnail_url",
        "topics", "targets", "subcategories", "raw_fields",
    ]
    date_names = [
        "published_at", "recruit_start_at", "recruit_end_at",
        "activity_start_at", "activity_end_at",
    ]
    ids = [row.get("id") for row in rows]
    collected = sorted(row["collected_at"] for row in rows if row.get("collected_at"))
    return {
        "input": path.name,
        "as_of_seoul": as_of.isoformat(),
        "scope": "local JSON snapshot; not live database counts",
        "total": len(rows),
        "unique_ids": len(set(ids)),
        "duplicate_id_rows": len(ids) - len(set(ids)),
        "sources": dict(sorted(Counter(row.get("source") for row in rows).items())),
        "categories": dict(sorted(Counter(category(row) for row in rows).items())),
        "statuses": dict(sorted(Counter(row.get("status") for row in rows).items())),
        "taxonomy_versions": dict(Counter(str(row.get("taxonomy_version")) for row in rows)),
        "collected_at_min": collected[0] if collected else None,
        "collected_at_max": collected[-1] if collected else None,
        "populated_fields": {
            field: sum(bool(row.get(field)) for row in rows) for field in field_names
        },
        "populated_dates": {
            field: sum(bool((row.get("dates") or {}).get(field)) for row in rows)
            for field in date_names
        },
        "date_only_fields": {
            field: sum(
                isinstance((row.get("dates") or {}).get(field), str)
                and len(row["dates"][field]) == 10 for row in rows
            ) for field in date_names
        },
        "classification_methods": dict(Counter(
            (row.get("details", {}).get("taxonomy") or {}).get("classification_method")
            for row in rows
        )),
        "classification_confidence": dict(Counter(
            (row.get("details", {}).get("taxonomy") or {}).get("confidence")
            for row in rows
        )),
        "open_with_expired_recruit_end": sum(
            row.get("status") == "OPEN" and expired(row) for row in rows
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(SEOUL).date())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = json.dumps(audit(args.input, args.as_of), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
