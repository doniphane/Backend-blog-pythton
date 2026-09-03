from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import security, storage
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import (
    EmailUpdate,
    PasswordChange,
    RoleUpdate,
    Token,
    UserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _is_bootstrap_admin(email: str) -> bool:
    """Vrai si l'email figure dans ADMIN_EMAILS (.env)."""
    allowed = {e.strip().lower() for e in settings.admin_emails.split(",") if e.strip()}
    return email.strip().lower() in allowed


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=security.hash_password(payload.password),
        # Par défaut tout nouveau compte est "user" (lecture seule).
        # Seuls les emails listés dans ADMIN_EMAILS démarrent administrateurs.
        role="admin" if _is_bootstrap_admin(payload.email) else "user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    token = security.create_access_token(subject=user.email)
    return {"access_token": token}


@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(security.get_current_user)):
    return current_user


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(security.require_admin),
):
    """Liste les comptes (admin uniquement — pour gérer les rôles)."""
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch("/users/{user_id}/role", response_model=UserOut)
def set_user_role(
    user_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.require_admin),
):
    """Promeut / rétrograde un compte (admin uniquement)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id and payload.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas retirer votre propre rôle admin",
        )
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.patch("/me/email", response_model=Token)
def update_email(
    payload: EmailUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    if not security.verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password incorrect"
        )
    if payload.email != current_user.email:
        if db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
            )
        current_user.email = payload.email
        db.commit()
    return {"access_token": security.create_access_token(subject=current_user.email)}


@router.post("/me/avatar", response_model=UserOut)
async def upload_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """Upload l'avatar de l'utilisateur connecté vers le bucket S3/MinIO.

    Le fichier est stocké dans le bucket ``MINIO_BUCKET`` (préfixe ``avatars/``)
    et l'URL publique est sauvegardée en base dans ``users.avatar_url``.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier doit être une image (JPEG, PNG, WebP, GIF).",
        )

    data = await file.read()
    try:
        url = storage.upload_avatar(data, file.content_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
        )

    # Supprime l'ancien avatar (best-effort) pour éviter les orphelins.
    if current_user.avatar_url:
        storage.delete_by_url(current_user.avatar_url)

    current_user.avatar_url = url
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me/avatar", response_model=UserOut)
def delete_my_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """Supprime l'avatar de l'utilisateur connecté."""
    if current_user.avatar_url:
        storage.delete_by_url(current_user.avatar_url)
        current_user.avatar_url = None
        db.commit()
        db.refresh(current_user)
    return current_user


@router.post("/change-password")
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    if not security.verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password incorrect"
        )
    current_user.hashed_password = security.hash_password(payload.new_password)
    db.commit()
    return {"detail": "Password updated"}
