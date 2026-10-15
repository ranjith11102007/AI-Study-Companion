"""Current-user profile: read and update the signed-in account.

Only the authenticated user's own row is ever touched. ``email`` is intentionally
read-only here — changing the address is an authentication concern (it needs
re-verification) and is handled by the auth endpoints, not this one.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserProfile, UserProfileUpdate

router = APIRouter()


def _serialize(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "display_name": user.display_name,
        "preferences": user.preferences or {},
        "email_verified": user.email_verified_at is not None,
        "created_at": user.created_at,
    }


@router.get("/users/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    """The real account behind the current token (never a client-side guess)."""
    return _serialize(current_user)


@router.patch("/users/me", response_model=UserProfile)
async def update_me(
    payload: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = payload.model_dump(exclude_unset=True)

    if data.get("name") is not None:
        current_user.name = data["name"].strip()

    if "display_name" in data:
        value = data["display_name"]
        if isinstance(value, str) and value.strip():
            current_user.display_name = value.strip()
        else:
            current_user.display_name = None

    # "preferences" explicitly present (even as null) is an update instruction.
    # null/empty object clears the stored bag; otherwise merge, so a partial
    # update cannot wipe the other keys.
    if "preferences" in data:
        if not data["preferences"]:
            current_user.preferences = {}
        else:
            merged = dict(current_user.preferences or {})
            merged.update(data["preferences"])
            current_user.preferences = merged

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return _serialize(current_user)
