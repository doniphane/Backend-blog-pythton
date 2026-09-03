import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        email = payload.get("sub")
        if email is None:
            raise credentials_exc
    except jwt.PyJWTError:
        raise credentials_exc

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exc
    return user


def get_optional_user(
    request: Request, db: Session = Depends(get_db)
) -> Optional[User]:
    """Utilisateur connecté s'il y a un token valide, sinon None (jamais 401).

    Permet aux routes publiques d'adapter leur réponse (ex. : masquer les
    brouillons aux non-admins) sans exiger d'authentification.
    """
    auth = request.headers.get("Authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    try:
        payload = jwt.decode(
            token.strip(), settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        email = payload.get("sub")
    except jwt.PyJWTError:
        return None
    if not email:
        return None
    return db.query(User).filter(User.email == email).first()


def is_admin_user(user: Optional[User]) -> bool:
    return user is not None and user.role == "admin"


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Garde les routes réservées aux administrateurs (publication d'articles...)."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé aux administrateurs",
        )
    return current_user
