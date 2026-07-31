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
    prefix="/api/job-postings",
    tags=["Job Postings"],
)


@router.get("")
def get_job_postings(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    employment_type: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    채용공고 목록을 조회한다.

    지원 기능:
    - 페이지네이션
    - 제목, 회사명, 직무명, 주소 검색
    - 고용형태 필터
    - 모집 중인 공고만 조회
    """

    conditions: list[str] = []
    parameters: dict[str, Any] = {}

    if keyword:
        conditions.append(
            """
            (
                title ILIKE :keyword
                OR organization_name ILIKE :keyword
                OR job_name ILIKE :keyword
                OR address ILIKE :keyword
            )
            """
        )
        parameters["keyword"] = f"%{keyword.strip()}%"

    if employment_type:
        conditions.append(
            "employment_type = :employment_type"
        )
        parameters["employment_type"] = (
            employment_type.strip()
        )

    if active_only:
        conditions.append(
            """
            (
                recruit_end_at IS NULL
                OR recruit_end_at >= NOW()
            )
            """
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
                FROM public.job_postings
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
                    title,
                    organization_name,
                    job_name,
                    job_code,
                    recruitment_count,
                    employment_type,
                    employment_type_raw,
                    salary_type,
                    salary_min,
                    salary_max,
                    salary_display,
                    education,
                    career,
                    industry,
                    address,
                    registration_at,
                    recruit_end_at,
                    source_code,
                    source_name,
                    source_url,
                    external_id,
                    collected_at,
                    verification_status,
                    created_at,
                    updated_at
                FROM public.job_postings
                {where_clause}
                ORDER BY
                    recruit_end_at ASC NULLS LAST,
                    registration_at DESC NULLS LAST,
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
                "keyword": keyword,
                "employment_type": employment_type,
                "active_only": active_only,
            },
        }

    except SQLAlchemyError as error:
        print(f"채용공고 목록 조회 오류: {error}")

        raise HTTPException(
            status_code=500,
            detail="채용공고 목록 조회에 실패했습니다.",
        ) from error


@router.get("/{posting_id}")
def get_job_posting_detail(
    posting_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    ID를 사용해 채용공고 상세 정보를 조회한다.
    """

    try:
        row = db.execute(
            text(
                """
                SELECT
                    id,
                    schema_version,
                    title,
                    organization_name,
                    job_name,
                    job_code,
                    recruitment_count,
                    employment_type,
                    employment_type_raw,
                    salary_type,
                    salary_min,
                    salary_max,
                    salary_display,
                    education,
                    career,
                    industry,
                    address,
                    registration_at,
                    recruit_end_at,
                    source_code,
                    source_name,
                    source_url,
                    external_id,
                    collected_at,
                    verification_status,
                    created_at,
                    updated_at
                FROM public.job_postings
                WHERE id = :posting_id
                LIMIT 1
                """
            ),
            {
                "posting_id": posting_id,
            },
        ).mappings().first()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="채용공고를 찾을 수 없습니다.",
            )

        return dict(row)

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"채용공고 상세 조회 오류: {error}")

        raise HTTPException(
            status_code=500,
            detail="채용공고 상세 조회에 실패했습니다.",
        ) from error