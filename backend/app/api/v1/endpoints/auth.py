from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserCreate, UserResponse, LoginRequest, Token
from app.services.auth import get_password_hash, verify_password, create_access_token

router = APIRouter()

@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("auth"))],
)
async def signup(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.email == user_in.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=user_in.name,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password)
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.post(
    "/signin",
    response_model=Token,
    dependencies=[Depends(rate_limit("auth", 30))],
)
async def signin(login_in: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.email == login_in.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}
