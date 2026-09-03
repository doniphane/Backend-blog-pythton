from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app import security, storage
from app.database import get_db
from app.models import Post, User
from app.schemas import PostCreate, PostOut, PostUpdate

router = APIRouter(prefix="/posts", tags=["posts"])


def _to_out(post: Post) -> PostOut:
    """Construit le PostOut en incluant les infos publiques de l'auteur."""
    owner = post.owner
    return PostOut(
        id=post.id,
        title=post.title,
        content=post.content,
        published=post.published,
        thumbnail_url=post.thumbnail_url,
        owner_id=post.owner_id,
        created_at=post.created_at,
        author_display_name=owner.display_name if owner else None,
        author_avatar_url=owner.avatar_url if owner else None,
    )


def _get_post_or_404(post_id: int, db: Session) -> Post:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


def _check_owner(post: Post, current_user: User) -> None:
    if post.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.require_admin),
):
    post = Post(owner_id=current_user.id, **payload.model_dump())
    db.add(post)
    db.commit()
    db.refresh(post)
    post.owner = current_user
    return _to_out(post)


@router.get("", response_model=list[PostOut])
def list_posts(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(security.get_optional_user),
):
    """Liste les articles. Les brouillons ne sont visibles que par les admins."""
    query = db.query(Post).options(joinedload(Post.owner))
    if not security.is_admin_user(current_user):
        query = query.filter(Post.published == True)  # noqa: E712
    posts = query.order_by(Post.created_at.desc()).all()
    return [_to_out(post) for post in posts]


@router.get("/{post_id}", response_model=PostOut)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(security.get_optional_user),
):
    """Détail d'un article. Un brouillon renvoie 404 pour les non-admins."""
    post = _get_post_or_404(post_id, db)
    if not post.published and not security.is_admin_user(current_user):
        raise HTTPException(status_code=404, detail="Post not found")
    return _to_out(post)


@router.patch("/{post_id}", response_model=PostOut)
def update_post(
    post_id: int,
    payload: PostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.require_admin),
):
    post = _get_post_or_404(post_id, db)
    _check_owner(post, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(post, field, value)
    db.commit()
    db.refresh(post)
    return _to_out(post)


@router.post("/{post_id}/thumbnail", response_model=PostOut)
async def upload_post_thumbnail(
    post_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(security.require_admin),
):
    """Upload la miniature d'un post vers le bucket S3/MinIO.

    Le fichier est stocké dans le bucket ``MINIO_BUCKET`` et l'URL publique
    est sauvegardée en base dans ``posts.thumbnail_url``.
    """
    post = _get_post_or_404(post_id, db)
    _check_owner(post, current_user)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier doit être une image (JPEG, PNG, WebP, GIF).",
        )

    data = await file.read()
    try:
        url = storage.upload_thumbnail(data, file.content_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
        )

    # Supprime l'ancienne miniature (best-effort) pour éviter les orphelins.
    if post.thumbnail_url:
        storage.delete_by_url(post.thumbnail_url)

    post.thumbnail_url = url
    db.commit()
    db.refresh(post)
    return _to_out(post)


@router.delete(
    "/{post_id}/thumbnail", response_model=PostOut, status_code=status.HTTP_200_OK
)
def delete_post_thumbnail(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.require_admin),
):
    post = _get_post_or_404(post_id, db)
    _check_owner(post, current_user)
    if post.thumbnail_url:
        storage.delete_by_url(post.thumbnail_url)
        post.thumbnail_url = None
        db.commit()
        db.refresh(post)
    return _to_out(post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.require_admin),
):
    post = _get_post_or_404(post_id, db)
    _check_owner(post, current_user)
    if post.thumbnail_url:
        storage.delete_by_url(post.thumbnail_url)
    db.delete(post)
    db.commit()
