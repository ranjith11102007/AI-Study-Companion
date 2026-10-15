from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # --- profile (migration 0004) ---
    # ``display_name`` is what the user chooses to be called; ``name`` stays the
    # signup name so nothing that already reads it changes meaning.
    display_name: Mapped[str | None] = mapped_column(String(120))
    # Free-form UI preferences (reduce motion, default course, ...). Stored
    # server-side so they follow the account instead of one browser.
    preferences: Mapped[dict | None] = mapped_column(JSONB)
    # Set only when the address is actually confirmed. Never assumed.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
