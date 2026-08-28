from fastapi import FastAPI

from app.routers import auth, health, posts

app = FastAPI(title="Blog API", version="0.1.0")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(posts.router)
