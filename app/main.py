from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import engine, get_db


app = FastAPI(
    title="모아봄 API",
    description="춘천 공공데이터 통합 플랫폼 백엔드 API",
    version="1.0.0",
)


# 프론트엔드에서 FastAPI를 호출할 수 있도록 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "message": "모아봄 백엔드 서버입니다."
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


@app.get("/health/db")
def database_health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected"
        }

    except SQLAlchemyError as error:
        print(f"데이터베이스 연결 오류: {error}")

        raise HTTPException(
            status_code=503,
            detail="데이터베이스에 연결할 수 없습니다."
        ) from error


@app.get("/api/opportunities")
def get_opportunities(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    공고, 교육, 행사, 관광지 등의 목록을 조회한다.

    지원 기능:
    - 페이지네이션
    - 카테고리 필터
    - 상태 필터
    - 제목 및 요약 검색
    """

    conditions: list[str] = []
    parameters: dict[str, Any] = {}

    if category:
        conditions.append("category = :category")
        parameters["category"] = category.upper()

    if status:
        conditions.append("status = :status")
        parameters["status"] = status.upper()

    if keyword:
        conditions.append(
            """
            (
                title ILIKE :keyword
                OR summary ILIKE :keyword
                OR source ILIKE :keyword
            )
            """
        )
        parameters["keyword"] = f"%{keyword}%"

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    offset = (page - 1) * size

    parameters["limit"] = size
    parameters["offset"] = offset

    try:
        count_query = text(
            f"""
            SELECT COUNT(*)
            FROM public.opportunities
            {where_clause}
            """
        )

        total = db.execute(
            count_query,
            parameters,
        ).scalar_one()

        list_query = text(
            f"""
            SELECT
                id,
                title,
                summary,
                category,
                status,
                organization,
                dates,
                targets,
                topics,
                location,
                thumbnail_url,
                source_logo_url,
                source,
                source_url,
                published_at,
                recruit_start_at,
                recruit_end_at,
                activity_start_at,
                activity_end_at,
                collected_at
            FROM public.opportunities
            {where_clause}
            ORDER BY
                published_at DESC NULLS LAST,
                created_at DESC
            LIMIT :limit
            OFFSET :offset
            """
        )

        rows = db.execute(
            list_query,
            parameters,
        ).mappings().all()

        items = [dict(row) for row in rows]

        total_pages = (
            (total + size - 1) // size
            if total > 0
            else 0
        )

        return {
            "items": items,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "total_pages": total_pages,
            },
            "filters": {
                "category": category,
                "status": status,
                "keyword": keyword,
            },
        }

    except SQLAlchemyError as error:
        print(f"목록 조회 오류: {error}")

        raise HTTPException(
            status_code=500,
            detail="목록 조회에 실패했습니다."
        ) from error


@app.get("/api/opportunities/{opportunity_id}")
def get_opportunity_detail(
    opportunity_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    ID를 사용해 하나의 항목을 상세 조회한다.
    """

    try:
        query = text(
            """
            SELECT
                id,
                title,
                summary,
                category,
                status,
                organization,
                dates,
                targets,
                topics,
                location,
                thumbnail_url,
                source_logo_url,
                source,
                source_url,
                details,
                published_at,
                recruit_start_at,
                recruit_end_at,
                activity_start_at,
                activity_end_at,
                collected_at,
                created_at,
                updated_at
            FROM public.opportunities
            WHERE id = :opportunity_id
            """
        )

        row = db.execute(
            query,
            {
                "opportunity_id": opportunity_id
            },
        ).mappings().first()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="해당 데이터를 찾을 수 없습니다."
            )

        return dict(row)

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"상세 조회 오류: {error}")

        raise HTTPException(
            status_code=500,
            detail="상세 정보 조회에 실패했습니다."
        ) from error