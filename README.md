# Backend-blog-python

API backend pour un blog, construite avec **FastAPI**, **PostgreSQL** et **JWT auth**.

## Fonctionnalités

- Inscription / connexion sécurisées (mot de passe haché en **bcrypt**, tokens **JWT** HS256)
- CRUD des articles protégés par authentification, liés à leur auteur
- Base de données **PostgreSQL** (pilote `psycopg`)
- Migrations **Alembic**
- Tout tourne dans **Docker** (Compose : API + Postgres)

## Structure

```
app/
  main.py          # application FastAPI
  config.py        # settings (pydantic-settings, .env)
  database.py      # engine SQLAlchemy + session
  models.py        # User, Post
  schemas.py       # schémas Pydantic
  security.py      # hachage, JWT, get_current_user
  routers/
    auth.py        # /auth/register, /auth/login, /auth/me
    posts.py       # /posts CRUD
    health.py      # /health
alembic/           # migrations
docker-compose.yml # api + db
Dockerfile
requirements.txt
```

## Démarrage avec Docker

```bash
cp .env.example .env        # mettre un SECRET_KEY fort en production
docker compose up --build
```

API disponible sur http://localhost:8000/docs (Swagger).

## Démarrage en local (sans Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Authentification (exemple)

```bash
curl -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"me@x.com","password":"secret123"}'

TOKEN=$(curl -X POST localhost:8000/auth/login \
  -d 'username=me@x.com&password=secret123' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -X POST localhost:8000/posts -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title":"Hello","content":"Mon premier post"}'
```
