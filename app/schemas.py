from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


UserEventType = Literal[
    "VIEW",
    "CLICK",
    "BOOKMARK",
    "APPLY",
]


class UserEventCreate(BaseModel):
    user_id: UUID
    opportunity_id: str
    event_type: UserEventType


class UserSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=6,
        max_length=100,
    )
    nickname: str = Field(
        min_length=2,
        max_length=30,
    )


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=6,
        max_length=100,
    )


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    nickname: str