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
    prefix="/api/career-jobs",
    tags=["Career Jobs"],
)


@router.get("")
def get_career_jobs(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    major: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    직업 목록을 조회한다.

    지원 기능:
    - 페이지네이션
    - 직업명 및 설명 검색
    - 관련 학과 필터
    """

    conditions: list[str] = []
    parameters: dict[str, Any] = {}

    if keyword:
        conditions.append(
            """
            (
                job_name ILIKE :keyword
                OR source_job_name ILIKE :keyword
                OR summary ILIKE :keyword
            )
            """
        )
        parameters["keyword"] = f"%{keyword.strip()}%"

    if major:
        conditions.append(
            "related_majors @> CAST(:major_json AS jsonb)"
        )
        parameters["major_json"] = f'["{major.strip()}"]'

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
                FROM public.career_jobs
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
                    job_name,
                    source_job_name,
                    summary,
                    related_jobs,
                    core_abilities,
                    aptitude,
                    interests,
                    related_majors,
                    related_certifications,
                    career_net_seq,
                    standard_job_code,
                    employment_job_code,
                    source_code,
                    source_name,
                    source_url,
                    external_id,
                    collected_at,
                    verification_status,
                    created_at,
                    updated_at
                FROM public.career_jobs
                {where_clause}
                ORDER BY job_name ASC
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
                "major": major,
            },
        }

    except SQLAlchemyError as error:
        print(f"직업 목록 조회 오류: {error}")

        raise HTTPException(
            status_code=500,
            detail="직업 목록 조회에 실패했습니다.",
        ) from error


@router.get("/{career_job_id}")
def get_career_job_detail(
    career_job_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    ID를 사용해 직업 상세 정보를 조회한다.
    """

    try:
        row = db.execute(
            text(
                """
                SELECT
                    id,
                    schema_version,
                    job_name,
                    source_job_name,
                    summary,
                    related_jobs,
                    core_abilities,
                    aptitude,
                    interests,
                    related_majors,
                    related_certifications,
                    career_net_seq,
                    standard_job_code,
                    employment_job_code,
                    source_code,
                    source_name,
                    source_url,
                    external_id,
                    collected_at,
                    verification_status,
                    created_at,
                    updated_at
                FROM public.career_jobs
                WHERE id = :career_job_id
                LIMIT 1
                """
            ),
            {
                "career_job_id": career_job_id,
            },
        ).mappings().first()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="직업 정보를 찾을 수 없습니다.",
            )

        return dict(row)

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"직업 상세 조회 오류: {error}")

        raise HTTPException(
            status_code=500,
            detail="직업 상세 조회에 실패했습니다.",
        ) from error