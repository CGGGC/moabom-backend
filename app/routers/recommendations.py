# app/routers/recommendations.py

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db


router = APIRouter(
    prefix="/api/recommendations",
    tags=["Recommendations"],
)


@router.get("")
def get_recommendations(
    user_id: UUID,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=16, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    사용자의 카테고리 선호 점수를 기준으로
    맞춤 공고를 조회한다.
    """

    offset = (page - 1) * size

    items = db.execute(
        text("""
            select
                o.*,

                coalesce(
                    p.score,
                    0
                ) as preference_score

            from public.opportunities o

            left join public.user_category_preferences p
                on p.user_id = :user_id
               and p.category = o.category

            where o.status in (
                'OPEN',
                'ALWAYS',
                'UPCOMING',
                'UNKNOWN'
            )

            order by
                coalesce(p.score, 0) desc,

                case o.status
                    when 'OPEN' then 1
                    when 'ALWAYS' then 2
                    when 'UPCOMING' then 3
                    when 'UNKNOWN' then 4
                    else 5
                end,

                o.recruit_end_at asc nulls last,
                o.published_at desc nulls last,
                o.id asc

            limit :size
            offset :offset
        """),
        {
            "user_id": str(user_id),
            "size": size,
            "offset": offset,
        },
    ).mappings().all()

    total = db.execute(
        text("""
            select count(*)
            from public.opportunities
            where status in (
                'OPEN',
                'ALWAYS',
                'UPCOMING',
                'UNKNOWN'
            )
        """),
    ).scalar_one()

    return {
        "items": [
            dict(item)
            for item in items
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
    }