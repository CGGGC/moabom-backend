from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    UserLoginRequest,
    UserSignupRequest,
)
from app.security import (
    hash_password,
    verify_password,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Auth"],
)


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
)
def signup(
    payload: UserSignupRequest,
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()
    nickname = payload.nickname.strip()

    existing_user = db.execute(
        text("""
            select id
            from public.users
            where lower(email) = :email
            limit 1
        """),
        {
            "email": email,
        },
    ).mappings().first()

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 가입된 이메일입니다.",
        )

    hashed_password = hash_password(
        payload.password
    )

    try:
        user = db.execute(
            text("""
                insert into public.users (
                    email,
                    password_hash,
                    nickname,
                    created_at,
                    updated_at
                )
                values (
                    :email,
                    :password_hash,
                    :nickname,
                    now(),
                    now()
                )
                returning
                    id,
                    email,
                    nickname,
                    created_at
            """),
            {
                "email": email,
                "password_hash": hashed_password,
                "nickname": nickname,
            },
        ).mappings().first()

        db.commit()

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 가입된 이메일입니다.",
        )

    except Exception:
        db.rollback()
        raise

    return {
        "message": "회원가입이 완료되었습니다.",
        "user": dict(user),
    }


@router.post("/login")
def login(
    payload: UserLoginRequest,
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()

    user = db.execute(
        text("""
            select
                id,
                email,
                nickname,
                password_hash,
                created_at
            from public.users
            where lower(email) = :email
            limit 1
        """),
        {
            "email": email,
        },
    ).mappings().first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    password_valid = verify_password(
        payload.password,
        user["password_hash"],
    )

    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    return {
        "message": "로그인에 성공했습니다.",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "nickname": user["nickname"],
            "created_at": user["created_at"],
        },
    }