import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    MetaData,
    Table,
    Text,
)

# python scripts/import_json.py로 실행해도 app을 찾을 수 있게
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import engine  # noqa: E402

DATA_DIR = PROJECT_ROOT / "data"

JSON_FILES = [
    "moabom_opportunities_v2.json",
]


metadata = MetaData()

opportunities = Table(
    "opportunities",
    metadata,
    Column("id", Text, primary_key=True),
    Column("title", Text, nullable=False),
    Column("summary", Text),
    Column("category", Text, nullable=False),
    Column("category_name", Text),
    Column("taxonomy_version", Text),
    Column("subcategories", JSON),
    Column("status", Text),
    Column("organization", JSON),
    Column("dates", JSON),
    Column("targets", JSON),
    Column("topics", JSON),
    Column("location", JSON),
    Column("thumbnail_url", Text),
    Column("source_logo_url", Text),
    Column("source", Text),
    Column("source_url", Text),
    Column("details", JSON),
    Column("raw_fields", JSON),
    Column("published_at", DateTime(timezone=True)),
    Column("recruit_start_at", DateTime(timezone=True)),
    Column("recruit_end_at", DateTime(timezone=True)),
    Column("activity_start_at", DateTime(timezone=True)),
    Column("activity_end_at", DateTime(timezone=True)),
    Column("collected_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
    schema="public",
)


def parse_datetime(value: Any) -> datetime | None:
    """JSON의 ISO 날짜 문자열을 Python datetime으로 변환한다."""

    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value

    if not isinstance(value, str):
        return None

    normalized_value = value.strip()

    # ISO 문자열 끝의 Z를 UTC 시간대 형식으로 변환
    if normalized_value.endswith("Z"):
        normalized_value = normalized_value[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(normalized_value)
    except ValueError:
        print(f"  [경고] 날짜 변환 실패: {value}")
        return None


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    """공통 JSON 한 건을 opportunities 테이블 구조로 변환한다."""

    dates = item.get("dates") or {}

    item_id = item.get("id")
    title = item.get("title")

    category_data = item.get("category")

    if isinstance(category_data, dict):
        category_code = category_data.get("code")
        category_name = category_data.get("name")
    else:
        # 구형 JSON 구조도 임시 호환
        category_code = category_data
        category_name = None

    if not item_id:
        raise ValueError("id가 없는 데이터입니다.")

    if not title:
        raise ValueError(
            f"title이 없는 데이터입니다. id={item_id}"
        )

    if not category_code:
        raise ValueError(
            f"category.code가 없는 데이터입니다. id={item_id}"
        )

    return {
        "id": str(item_id),
        "title": str(title),
        "summary": item.get("summary"),

        "category": str(category_code).upper(),
        "category_name": (
            str(category_name)
            if category_name
            else None
        ),
        "taxonomy_version": item.get("taxonomy_version"),
        "subcategories": item.get("subcategories") or [],

        "status": (
            str(item["status"]).upper()
            if item.get("status")
            else None
        ),

        "organization": item.get("organization") or {},
        "dates": dates,
        "targets": item.get("targets") or [],
        "topics": item.get("topics") or [],
        "location": item.get("location") or {},

        "thumbnail_url": item.get("thumbnail_url"),
        "source_logo_url": item.get("source_logo_url"),
        "source": item.get("source"),
        "source_url": item.get("source_url"),

        "details": item.get("details") or {},
        "raw_fields": item.get("raw_fields") or {},

        "published_at": parse_datetime(
            dates.get("published_at")
        ),
        "recruit_start_at": parse_datetime(
            dates.get("recruit_start_at")
        ),
        "recruit_end_at": parse_datetime(
            dates.get("recruit_end_at")
        ),
        "activity_start_at": parse_datetime(
            dates.get("activity_start_at")
        ),
        "activity_end_at": parse_datetime(
            dates.get("activity_end_at")
        ),
        "collected_at": parse_datetime(
            item.get("collected_at")
        ),
    }

def load_json_file(file_path: Path) -> list[dict[str, Any]]:
    """JSON 파일을 읽고 최상위 구조가 배열인지 검사한다."""

    if not file_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    with file_path.open(
        mode="r",
        encoding="utf-8-sig",
    ) as json_file:
        data = json.load(json_file)

    if not isinstance(data, list):
        raise ValueError(f"{file_path.name}의 최상위 데이터가 배열이 아닙니다.")

    return data


def upsert_items(
    connection,
    items: list[dict[str, Any]],
) -> tuple[int, int]:
    """
    여러 데이터를 Upsert한다.

    반환값:
    - 성공 건수
    - 실패 건수
    """

    success_count = 0
    failure_count = 0

    for original_item in items:
        item_id = original_item.get("id", "UNKNOWN")

        try:
            normalized_item = normalize_item(original_item)

            statement = insert(opportunities).values(**normalized_item)

            # 같은 id가 이미 있으면 아래 컬럼을 갱신
            update_columns = {
                "title": statement.excluded.title,
                "summary": statement.excluded.summary,
                "category": statement.excluded.category,
                "category_name": statement.excluded.category_name,
                "taxonomy_version": statement.excluded.taxonomy_version,
                "subcategories": statement.excluded.subcategories,
                "status": statement.excluded.status,
                "organization": statement.excluded.organization,
                "dates": statement.excluded.dates,
                "targets": statement.excluded.targets,
                "topics": statement.excluded.topics,
                "location": statement.excluded.location,
                "thumbnail_url": statement.excluded.thumbnail_url,
                "source_logo_url": statement.excluded.source_logo_url,
                "source": statement.excluded.source,
                "source_url": statement.excluded.source_url,
                "details": statement.excluded.details,
                "raw_fields": statement.excluded.raw_fields,
                "published_at": statement.excluded.published_at,
                "recruit_start_at": (statement.excluded.recruit_start_at),
                "recruit_end_at": (statement.excluded.recruit_end_at),
                "activity_start_at": (statement.excluded.activity_start_at),
                "activity_end_at": (statement.excluded.activity_end_at),
                "collected_at": statement.excluded.collected_at,
                "updated_at": datetime.now().astimezone(),
            }

            upsert_statement = statement.on_conflict_do_update(
                index_elements=["id"],
                set_=update_columns,
            )

            connection.execute(upsert_statement)
            success_count += 1

        except (ValueError, TypeError) as error:
            failure_count += 1
            print(f"  [실패] id={item_id}: {error}")

    return success_count, failure_count


def main() -> None:
    total_loaded = 0
    total_success = 0
    total_failure = 0

    print("=" * 60)
    print("모아봄 JSON 데이터 적재를 시작합니다.")
    print(f"데이터 폴더: {DATA_DIR}")
    print("=" * 60)

    try:
        # begin()을 사용하면 성공 시 COMMIT,
        # 예외 발생 시 자동 ROLLBACK된다.
        with engine.begin() as connection:
            for filename in JSON_FILES:
                file_path = DATA_DIR / filename

                print(f"\n[파일 읽기] {filename}")

                try:
                    items = load_json_file(file_path)
                except (
                    FileNotFoundError,
                    json.JSONDecodeError,
                    ValueError,
                ) as error:
                    print(f"  [파일 실패] {error}")
                    total_failure += 1
                    continue

                print(f"  읽은 데이터: {len(items)}건")
                total_loaded += len(items)

                success_count, failure_count = upsert_items(
                    connection,
                    items,
                )

                total_success += success_count
                total_failure += failure_count

                print(f"  적재 성공: {success_count}건")
                print(f"  적재 실패: {failure_count}건")

    except SQLAlchemyError as error:
        print("\n[DB 오류] 적재가 중단되었습니다.")
        print(error)
        raise SystemExit(1) from error

    print("\n" + "=" * 60)
    print("데이터 적재가 완료되었습니다.")
    print(f"읽은 데이터: {total_loaded}건")
    print(f"적재 성공: {total_success}건")
    print(f"적재 실패: {total_failure}건")
    print("=" * 60)


if __name__ == "__main__":
    main()
