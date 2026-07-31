from math import ceil
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db


router = APIRouter(
    prefix="/api/housing",
    tags=["Housing"],
)


def build_conditions(
    province: str | None,
    city: str | None,
    housing_type: str | None,
    transaction_type: str | None,
    area_min: float | None,
    area_max: float | None,
) -> tuple[list[str], dict[str, Any]]:
    conditions: list[str] = []
    parameters: dict[str, Any] = {}

    if province:
        conditions.append(
            "province = :province"
        )
        parameters["province"] = province.strip()

    if city:
        conditions.append(
            "city = :city"
        )
        parameters["city"] = city.strip()

    if housing_type:
        conditions.append(
            "housing_type = :housing_type"
        )
        parameters["housing_type"] = (
            housing_type.strip()
        )

    if transaction_type:
        conditions.append(
            "transaction_type = :transaction_type"
        )
        parameters["transaction_type"] = (
            transaction_type.strip()
        )

    if area_min is not None:
        conditions.append(
            "exclusive_area_m2 >= :area_min"
        )
        parameters["area_min"] = area_min

    if area_max is not None:
        conditions.append(
            "exclusive_area_m2 <= :area_max"
        )
        parameters["area_max"] = area_max

    return conditions, parameters


@router.get("/transactions")
def get_housing_transactions(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    province: str | None = Query(default=None),
    city: str | None = Query(default=None),
    housing_type: str | None = Query(default=None),
    transaction_type: str | None = Query(default=None),
    area_min: float | None = Query(
        default=None,
        ge=0,
    ),
    area_max: float | None = Query(
        default=None,
        ge=0,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    주거 거래 목록을 조회한다.

    지원 기능:
    - 페이지네이션
    - 지역 필터
    - 주택유형 필터
    - 전세/월세 필터
    - 전용면적 범위 필터
    """

    conditions, parameters = build_conditions(
        province=province,
        city=city,
        housing_type=housing_type,
        transaction_type=transaction_type,
        area_min=area_min,
        area_max=area_max,
    )

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(
            conditions
        )

    offset = (page - 1) * size
    parameters["limit"] = size
    parameters["offset"] = offset

    try:
        total = db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM public.housing_transactions
                {where_clause}
                """
            ),
            parameters,
        ).scalar_one()

        rows = db.execute(
            text(
                f"""
                SELECT
                    id,
                    schema_version,
                    province,
                    city,
                    district,
                    legal_dong,
                    full_address,
                    jibun,
                    road_address,
                    housing_type,
                    building_name,
                    exclusive_area_m2,
                    floor,
                    built_year,
                    contract_date,
                    transaction_type,
                    deposit,
                    monthly_rent,
                    renewal_type,
                    contract_term,
                    previous_deposit,
                    previous_monthly_rent,
                    source_code,
                    source_name,
                    source_url,
                    external_id,
                    collected_at,
                    verification_status,
                    created_at,
                    updated_at
                FROM public.housing_transactions
                {where_clause}
                ORDER BY
                    contract_date DESC NULLS LAST,
                    id ASC
                LIMIT :limit
                OFFSET :offset
                """
            ),
            parameters,
        ).mappings().all()

        return {
            "items": [
                dict(row)
                for row in rows
            ],
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "total_pages": (
                    ceil(total / size)
                    if total > 0
                    else 0
                ),
            },
            "filters": {
                "province": province,
                "city": city,
                "housing_type": housing_type,
                "transaction_type": transaction_type,
                "area_min": area_min,
                "area_max": area_max,
            },
        }

    except SQLAlchemyError as error:
        print(f"주거 거래 목록 조회 오류: {error}")

        raise HTTPException(
            status_code=500,
            detail="주거 거래 목록 조회에 실패했습니다.",
        ) from error


@router.get("/compare")
def compare_housing(
    housing_type: str | None = Query(default=None),
    transaction_type: str | None = Query(default=None),
    area_min: float | None = Query(
        default=None,
        ge=0,
    ),
    area_max: float | None = Query(
        default=None,
        ge=0,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    동일한 주택 조건에서 춘천과 서울의
    평균 보증금, 월세, 면적을 비교한다.
    """

    conditions, parameters = build_conditions(
        province=None,
        city=None,
        housing_type=housing_type,
        transaction_type=transaction_type,
        area_min=area_min,
        area_max=area_max,
    )

    conditions.append(
        """
        (
            province = '서울특별시'
            OR city = '춘천시'
            OR full_address ILIKE '%춘천%'
        )
        """
    )

    where_clause = "WHERE " + " AND ".join(
        conditions
    )

    try:
        rows = db.execute(
            text(
                f"""
                SELECT
                    CASE
                        WHEN province = '서울특별시'
                            THEN '서울특별시'
                        WHEN city = '춘천시'
                            OR full_address ILIKE '%춘천%'
                            THEN '춘천시'
                        ELSE '기타'
                    END AS region_name,

                    COUNT(*) AS sample_count,

                    AVG(deposit)
                        FILTER (
                            WHERE deposit IS NOT NULL
                        ) AS average_deposit,

                    PERCENTILE_CONT(0.5)
                        WITHIN GROUP (
                            ORDER BY deposit
                        )
                        FILTER (
                            WHERE deposit IS NOT NULL
                        ) AS median_deposit,

                    AVG(monthly_rent)
                        FILTER (
                            WHERE monthly_rent IS NOT NULL
                        ) AS average_monthly_rent,

                    PERCENTILE_CONT(0.5)
                        WITHIN GROUP (
                            ORDER BY monthly_rent
                        )
                        FILTER (
                            WHERE monthly_rent IS NOT NULL
                        ) AS median_monthly_rent,

                    AVG(exclusive_area_m2)
                        FILTER (
                            WHERE exclusive_area_m2
                            IS NOT NULL
                        ) AS average_area_m2

                FROM public.housing_transactions
                {where_clause}

                GROUP BY
                    CASE
                        WHEN province = '서울특별시'
                            THEN '서울특별시'
                        WHEN city = '춘천시'
                            OR full_address ILIKE '%춘천%'
                            THEN '춘천시'
                        ELSE '기타'
                    END

                ORDER BY region_name
                """
            ),
            parameters,
        ).mappings().all()

        regions = []

        for row in rows:
            item = dict(row)

            for field in [
                "average_deposit",
                "median_deposit",
                "average_monthly_rent",
                "median_monthly_rent",
                "average_area_m2",
            ]:
                if item[field] is not None:
                    item[field] = float(
                        item[field]
                    )

            regions.append(item)

        return {
            "conditions": {
                "housing_type": housing_type,
                "transaction_type": (
                    transaction_type
                ),
                "area_min": area_min,
                "area_max": area_max,
            },
            "regions": regions,
        }

    except SQLAlchemyError as error:
        print(f"주거 비교 조회 오류: {error}")

        raise HTTPException(
            status_code=500,
            detail="주거 비교 조회에 실패했습니다.",
        ) from error