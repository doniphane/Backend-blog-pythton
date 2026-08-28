from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import security
from app.database import get_db
from app.models import Post, User
from app.schemas import PostCreate, PostOut

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    post = Post(owner_id=current_user.id, **payload.model_dump())
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.get("", response_model=list[PostOut])
def list_posts(db: Session = Depends(get_db)):
    return db.query(Post).all()


@router.get("/{post_id}", response_model=PostOut)
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    db.delete(post)
    db.commit()
