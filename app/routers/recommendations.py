from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(
    prefix="/api/recommendations",
    tags=["Recommendations"],
)


@router.get("")
def get_recommendations(
    user_id: UUID,
    page: int = Query(
        default=1,
        ge=1,
    ),
    size: int = Query(
        default=16,
        ge=1,
        le=800,
    ),
    category: str | None = Query(
        default=None,
    ),
    db: Session = Depends(get_db),
):
    """
    사용자 선호도와 지역 우선순위를 기준으로
    맞춤 공고 목록을 반환한다.

    지역 우선순위:
    - 공모전·해커톤: 전국/온라인 우선
    - 나머지 카테고리: 춘천 우선
    """

    offset = (page - 1) * size

    normalized_category = category.strip().upper() if category else None

    try:
        items = (
            db.execute(
                text("""
                WITH scored_opportunities AS (
                    SELECT
                        o.*,

                        COALESCE(
                            p.score,
                            0
                        ) AS preference_score,

                        CASE
                            /*
                            공모전과 해커톤은
                            전국·온라인 참여 가능 여부를 우선한다.
                            */
                            WHEN o.category IN (
                                'CONTEST',
                                'HACKATHON'
                            )
                            THEN
                                CASE
                                    WHEN
                                        o.location::text
                                            ILIKE '%전국%'
                                        OR o.location::text
                                            ILIKE '%온라인%'
                                        OR o.title
                                            ILIKE '%전국%'
                                        OR o.title
                                            ILIKE '%온라인%'
                                        OR o.summary
                                            ILIKE '%전국%'
                                        OR o.summary
                                            ILIKE '%온라인%'
                                    THEN 10

                                    WHEN
                                        o.location::text
                                            ILIKE '%춘천%'
                                        OR o.title
                                            ILIKE '%춘천%'
                                        OR o.summary
                                            ILIKE '%춘천%'
                                    THEN 7

                                    WHEN
                                        o.location::text
                                            ILIKE '%강원%'
                                    THEN 5

                                    ELSE 2
                                END

                            /*
                            나머지 카테고리는
                            춘천 관련 공고를 우선한다.
                            */
                            ELSE
                                CASE
                                    WHEN
                                        o.location::text
                                            ILIKE '%춘천%'
                                        OR o.title
                                            ILIKE '%춘천%'
                                        OR o.summary
                                            ILIKE '%춘천%'
                                    THEN 10

                                    WHEN
                                        o.location::text
                                            ILIKE '%강원%'
                                        OR o.title
                                            ILIKE '%강원%'
                                        OR o.summary
                                            ILIKE '%강원%'
                                    THEN 6

                                    WHEN
                                        o.location::text
                                            ILIKE '%전국%'
                                        OR o.location::text
                                            ILIKE '%온라인%'
                                        OR o.title
                                            ILIKE '%전국%'
                                        OR o.title
                                            ILIKE '%온라인%'
                                        OR o.summary
                                            ILIKE '%전국%'
                                        OR o.summary
                                            ILIKE '%온라인%'
                                    THEN 3

                                    ELSE 0
                                END
                        END AS region_score

                    FROM public.opportunities AS o

                    LEFT JOIN public.user_category_preferences AS p
                        ON p.user_id = :user_id
                       AND p.category = o.category

                    WHERE o.status IN (
                        'OPEN',
                        'ALWAYS',
                        'UPCOMING',
                        'UNKNOWN'
                    )
                    AND (
                        o.recruit_end_at IS NULL
                        OR o.recruit_end_at >= CURRENT_DATE
                    )

                    AND (
                        CAST(:category AS TEXT) IS NULL
                        OR o.category = :category
                    )
                )

                SELECT
                    scored_opportunities.*,

                    (
                        preference_score
                        + region_score
                    ) AS recommendation_score

                FROM scored_opportunities

                ORDER BY
                    recommendation_score DESC,

                    CASE status
                        WHEN 'OPEN' THEN 1
                        WHEN 'ALWAYS' THEN 2
                        WHEN 'UPCOMING' THEN 3
                        WHEN 'UNKNOWN' THEN 4
                        ELSE 5
                    END,

                    recruit_end_at ASC NULLS LAST,
                    published_at DESC NULLS LAST,
                    id ASC

                LIMIT :size
                OFFSET :offset
                """),
                {
                    "user_id": str(user_id),
                    "category": normalized_category,
                    "size": size,
                    "offset": offset,
                },
            )
            .mappings()
            .all()
        )

        total = db.execute(
            text("""
                SELECT COUNT(*)
                FROM public.opportunities

                WHERE status IN (
                    'OPEN',
                    'ALWAYS',
                    'UPCOMING',
                    'UNKNOWN'
                )
                AND (
                    recruit_end_at IS NULL
                    OR recruit_end_at >= CURRENT_DATE
                )

                AND (
                    CAST(:category AS TEXT) IS NULL
                    OR category = :category
                )
                """),
            {
                "category": normalized_category,
            },
        ).scalar_one()

    except SQLAlchemyError as error:
        print(f"추천 목록 조회 오류: {error}")

        raise

    return {
        "items": [dict(item) for item in items],
        "pagination": {
            "page": page,
            "size": size,
            "total": total,
            "total_pages": (ceil(total / size) if total > 0 else 0),
        },
        "filters": {
            "category": normalized_category,
        },
        "scoring": {
            "formula": ("preference_score + region_score"),
            "contest_hackathon_priority": ("NATIONWIDE_ONLINE"),
            "other_category_priority": ("CHUNCHEON"),
        },
    }
