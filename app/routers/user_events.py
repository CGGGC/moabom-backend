# app/routers/user_events.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import UserEventCreate


router = APIRouter(
    prefix="/api/user-events",
    tags=["User Events"],
)


EVENT_SETTINGS = {
    "VIEW": {
        "score": 1,
        "view_count": 1,
        "click_count": 0,
        "bookmark_count": 0,
        "apply_count": 0,
    },
    "CLICK": {
        "score": 3,
        "view_count": 0,
        "click_count": 1,
        "bookmark_count": 0,
        "apply_count": 0,
    },
    "BOOKMARK": {
        "score": 5,
        "view_count": 0,
        "click_count": 0,
        "bookmark_count": 1,
        "apply_count": 0,
    },
    "APPLY": {
        "score": 8,
        "view_count": 0,
        "click_count": 0,
        "bookmark_count": 0,
        "apply_count": 1,
    },
}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_user_event(
    payload: UserEventCreate,
    db: Session = Depends(get_db),
):
    # 1. 해당 공고가 실제로 존재하는지 확인
    opportunity = db.execute(
        text("""
            select
                id,
                title,
                category
            from public.opportunities
            where id = :opportunity_id
            limit 1
        """),
        {
            "opportunity_id": payload.opportunity_id,
        },
    ).mappings().first()

    if opportunity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 공고를 찾을 수 없습니다.",
        )

    event_setting = EVENT_SETTINGS[payload.event_type]

    try:
        # 2. 사용자 행동 원본 저장
        event = db.execute(
            text("""
                insert into public.user_activity_events (
                    user_id,
                    opportunity_id,
                    event_type,
                    category,
                    created_at
                )
                values (
                    :user_id,
                    :opportunity_id,
                    :event_type,
                    :category,
                    now()
                )
                returning
                    id,
                    user_id,
                    opportunity_id,
                    event_type,
                    category,
                    created_at
            """),
            {
                "user_id": str(payload.user_id),
                "opportunity_id": payload.opportunity_id,
                "event_type": payload.event_type,
                "category": opportunity["category"],
            },
        ).mappings().first()

        # 3. 사용자별 카테고리 선호도 증가
        preference = db.execute(
            text("""
                insert into public.user_category_preferences (
                    user_id,
                    category,
                    score,
                    view_count,
                    click_count,
                    bookmark_count,
                    apply_count,
                    updated_at
                )
                values (
                    :user_id,
                    :category,
                    :score,
                    :view_count,
                    :click_count,
                    :bookmark_count,
                    :apply_count,
                    now()
                )
                on conflict (user_id, category)
                do update set
                    score =
                        user_category_preferences.score
                        + excluded.score,

                    view_count =
                        user_category_preferences.view_count
                        + excluded.view_count,

                    click_count =
                        user_category_preferences.click_count
                        + excluded.click_count,

                    bookmark_count =
                        user_category_preferences.bookmark_count
                        + excluded.bookmark_count,

                    apply_count =
                        user_category_preferences.apply_count
                        + excluded.apply_count,

                    updated_at = now()

                returning
                    user_id,
                    category,
                    score,
                    view_count,
                    click_count,
                    bookmark_count,
                    apply_count,
                    updated_at
            """),
            {
                "user_id": str(payload.user_id),
                "category": opportunity["category"],
                "score": event_setting["score"],
                "view_count": event_setting["view_count"],
                "click_count": event_setting["click_count"],
                "bookmark_count": event_setting["bookmark_count"],
                "apply_count": event_setting["apply_count"],
            },
        ).mappings().first()

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "recorded": True,
        "opportunity": {
            "id": opportunity["id"],
            "title": opportunity["title"],
            "category": opportunity["category"],
        },
        "event": dict(event),
        "preference": dict(preference),
    }