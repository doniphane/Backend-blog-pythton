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
Console MinIO sur http://localhost:9001.

## Miniatures des posts (MinIO / S3)

- Les miniatures sont stockées dans le bucket S3 **minuaturepost** (MinIO `localhost:9000`).
- Toute la config est en variables d'environnement (voir `.env.example`) :
  `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`,
  `MINIO_BUCKET`, `MINIO_SECURE`, `MINIO_PUBLIC_URL`.
- La colonne `posts.thumbnail_url` contient l'URL publique du fichier.
- Endpoints (authentifié, propriétaire du post) :
  - `POST /posts/{id}/thumbnail` (multipart `file` : JPEG/PNG/WebP/GIF, max 5 Mo)
  - `DELETE /posts/{id}/thumbnail`
  - `PATCH /posts/{id}` (peut aussi définir `thumbnail_url` directement)

```bash
curl -X POST localhost:8000/posts/1/thumbnail -H "Authorization: Bearer $TOKEN" \
  -F "file=@miniature.png"
```

## Rôles : user / admin

- Tout nouveau compte est créé avec le rôle **`user`** (lecture des articles en entier,
  pas de publication).
- Seuls les **`admin`** peuvent créer / modifier / supprimer des articles
  (`POST/PATCH/DELETE /posts…` → `403` sinon).
- Les **brouillons** (`published: false`) sont invisibles pour tout le monde sauf les
  admins : exclus de `GET /posts` et `404` sur `GET /posts/{id}` pour les non-admins.
- Emails administrateurs au démarrage via `.env` : `ADMIN_EMAILS=moi@exemple.com`.
- Gestion des rôles (admin uniquement) :
  - `GET /auth/users` — liste des comptes
  - `PATCH /auth/users/{id}/role` — `{"role": "admin" | "user"}`
- Promotion manuelle d'un compte existant :
  ```bash
  .venv/bin/python scripts/promote_admin.py moi@exemple.com
  ```

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
