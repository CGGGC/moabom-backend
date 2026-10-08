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
    """
    이메일, 비밀번호, 닉네임을 사용해 회원가입한다.

    현재는 Supabase Auth가 아니라
    public.users 테이블을 직접 사용하는 임시 인증 구조다.
    """

    email = payload.email.strip().lower()
    nickname = payload.nickname.strip()

    # 같은 이메일이 이미 등록되어 있는지 확인
    existing_user = db.execute(
        text(
            """
            SELECT id
            FROM public.users
            WHERE LOWER(email) = :email
            LIMIT 1
            """
        ),
        {
            "email": email,
        },
    ).mappings().first()

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 가입된 이메일입니다.",
        )

    # 평문 비밀번호를 저장하지 않고 해시값으로 변환
    hashed_password = hash_password(
        payload.password
    )

    try:
        user = db.execute(
            text(
                """
                INSERT INTO public.users (
                    email,
                    password_hash,
                    nickname,
                    created_at,
                    updated_at
                )
                VALUES (
                    :email,
                    :password_hash,
                    :nickname,
                    NOW(),
                    NOW()
                )
                RETURNING
                    id,
                    email,
                    nickname,
                    created_at
                """
            ),
            {
                "email": email,
                "password_hash": hashed_password,
                "nickname": nickname,
            },
        ).mappings().first()

        db.commit()

    except IntegrityError as error:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 가입된 이메일입니다.",
        ) from error

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
    """
    이메일과 비밀번호를 검증해 로그인한다.

    현재는 JWT를 발급하지 않고 사용자 정보만 반환한다.
    """

    email = payload.email.strip().lower()

    user = db.execute(
        text(
            """
            SELECT
                id,
                email,
                nickname,
                password_hash,
                created_at
            FROM public.users
            WHERE LOWER(email) = :email
            LIMIT 1
            """
        ),
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