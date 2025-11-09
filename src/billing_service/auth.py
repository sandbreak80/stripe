"""Authentication middleware for per-app API keys."""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from billing_service.database import get_db
from billing_service.models import App


def get_app_from_api_key(api_key: str, db: Session) -> App | None:
    """Get app from API key."""
    return db.query(App).filter(App.api_key == api_key, App.active == True).first()  # noqa: E712


async def verify_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> App:
    """Verify API key and return associated app."""
    app = get_app_from_api_key(x_api_key, db)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return app
