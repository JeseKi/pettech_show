# -*- coding: utf-8 -*-
"""Registration and verification code routes."""

import re
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.server.database import get_db
from .. import service
from ..models import User
from ..schemas import (
    UserCreate,
    UserProfile,
    UserRegister,
    UserRegisterWithCode,
    VerificationCodeRequest,
)
from .base import router


@router.post(
    "/register",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
    description="使用用户名和密码创建新用户账户，系统自动生成内部邮箱",
    response_description="返回新创建的用户信息",
    responses={
        201: {"description": "用户创建成功"},
        400: {"description": "用户名已被注册"},
    },
)
async def register_user(
    request: Request,
    user_data: UserRegister,
    db: Session = Depends(get_db),
):
    await service.verify_turnstile_token(
        request=request,
        token=user_data.turnstile_token,
        action="auth_register",
    )
    db_user = service.get_user_by_username(db, username=user_data.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已被注册"
        )

    generated_email = _generate_internal_email(db, user_data.username)
    user_create = UserCreate(
        username=user_data.username, email=generated_email, password=user_data.password
    )
    new_user = service.create_user(db=db, user_data=user_create)
    return new_user


@router.post(
    "/send-verification-code",
    summary="发送邮箱验证码",
    responses={
        200: {"description": "验证码发送成功"},
        400: {"description": "邮箱已被注册"},
        429: {"description": "发送过于频繁"},
        500: {"description": "验证码发送失败"},
    },
)
async def send_verification_code(
    request: Request,
    payload: VerificationCodeRequest,
    db: Session = Depends(get_db),
):
    await service.verify_turnstile_token(
        request=request,
        token=payload.turnstile_token,
        action="auth_send_verification_code",
    )

    normalized_email = payload.email.strip().lower()
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        return {"message": "验证码已发送"}

    try:
        service.send_verification_code(normalized_email)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        )
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="验证码发送失败"
        )
    return {"message": "验证码已发送"}


@router.post(
    "/register-with-code",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
    summary="使用验证码注册用户",
    description="使用邮箱验证码创建新用户账户",
    response_description="返回新创建的用户信息",
    responses={
        201: {"description": "用户创建成功"},
        400: {"description": "用户名或邮箱已被注册 / 验证码无效"},
    },
)
async def register_user_with_code(
    request: Request,
    user_data: UserRegisterWithCode,
    db: Session = Depends(get_db),
):
    await service.verify_turnstile_token(
        request=request,
        token=user_data.turnstile_token,
        action="auth_register_with_code",
    )
    normalized_email = user_data.email.strip().lower()
    db_user = service.get_user_by_username(db, username=user_data.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已被注册"
        )

    existing_email = db.query(User).filter(User.email == normalized_email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册"
        )

    if not service.verify_code(normalized_email, user_data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="验证码无效或已过期"
        )

    user_create = UserCreate(
        username=user_data.username, email=normalized_email, password=user_data.password
    )
    new_user = service.create_user(db=db, user_data=user_create)
    return new_user


def _generate_internal_email(db: Session, username: str) -> str:
    local_part = re.sub(r"[^a-z0-9._-]+", "-", username.strip().lower()).strip(".-_")
    if not local_part:
        local_part = "user"
    local_part = local_part[:48]
    email = f"{local_part}@mail.kispace.cc"
    if not db.query(User).filter(User.email == email).first():
        return email

    for _ in range(12):
        candidate = f"{local_part}-{uuid4().hex[:8]}@mail.kispace.cc"
        if not db.query(User).filter(User.email == candidate).first():
            return candidate

    return f"user-{uuid4().hex}@mail.kispace.cc"
