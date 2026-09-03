# API — Guide d'intégration frontend (Next.js)

Ce document décrit **toutes les routes** de l'API backend à consommer depuis le frontend Next.js.
L'authentification repose sur **JWT** : après le login, le backend renvoie un `access_token` que le frontend doit
renvoyer dans le header `Authorization: Bearer <token>` pour chaque route protégée.

> **Base URL** (local) : `http://localhost:8000`
> Swagger interactif : `http://localhost:8000/docs`

---

## 1. Schémas (formes des données)

```ts
// Entrée inscription
interface UserCreate {
  email: string;      // email valide
  password: string;   // 8 à 128 caractères
}

// Sortie utilisateur
interface UserOut {
  id: number;
  email: string;
  created_at: string; // ISO 8601
}

// Réponse login
interface Token {
  access_token: string;
  token_type: string;   // "bearer"
}

// Entrée article
interface PostCreate {
  title: string;
  content: string;
  published?: boolean;  // défaut : true
}

// Sortie article
interface PostOut {
  id: number;
  title: string;
  content: string;
  published: boolean;
  owner_id: number;
  created_at: string;
}
```

---

## 2. Flux d'authentification

1. **Inscription** → `POST /auth/register` (JSON)
2. **Connexion** → `POST /auth/login` (**form-urlencoded**, pas du JSON !) → récupère `access_token`
3. **Stocker le token** côté frontend (localStorage ou cookie httpOnly)
4. **Appels protégés** → ajouter `Authorization: Bearer <access_token>`
5. **Profil** → `GET /auth/me` pour vérifier/charger l'utilisateur connecté

⚠️ `/auth/login` utilise le format **OAuth2 Password** : le corps doit être
`application/x-www-form-urlencoded` avec les champs `username` (= email) et `password`.

---

## 3. Routes

### `GET /health`
Santé du service. Public.

**Réponse** `200` :
```json
{ "status": "ok" }
```

```ts
const res = await fetch(`${BASE}/health`);
```

---

### `POST /auth/register`
Crée un compte. Public.

**Body (JSON)** :
```json
{ "email": "me@x.com", "password": "secret123" }
```

**Réponses** :
- `201` → `UserOut`
- `400` → `{ "detail": "Email already registered" }` (email déjà pris)

```ts
const res = await fetch(`${BASE}/auth/register`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email, password }),
});
if (!res.ok) throw new Error((await res.json()).detail);
const user: UserOut = await res.json();
```

---

### `POST /auth/login`
Renvoie le JWT. Public. **Body en `form-urlencoded`**.

**Body** :
```
username=me@x.com&password=secret123
```

**Réponses** :
- `200` → `Token`
- `401` → `{ "detail": "Invalid credentials" }`

```ts
const body = new URLSearchParams({ username: email, password });
const res = await fetch(`${BASE}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
  body,
});
if (!res.ok) throw new Error((await res.json()).detail);
const { access_token } = (await res.json()) as Token;
// Stocke access_token (ex: localStorage.setItem("token", access_token))
```

---

### `GET /auth/me`
Renvoie l'utilisateur connecté. **Protégée** (Bearer).

**Headers** : `Authorization: Bearer <access_token>`

**Réponses** :
- `200` → `UserOut`
- `401` → token absent/invalide/expire

```ts
const res = await fetch(`${BASE}/auth/me`, {
  headers: { Authorization: `Bearer ${token}` },
});
if (res.status === 401) {
  /* déconnecte l'utilisateur */
}
const user: UserOut = await res.json();
```

---

### `PATCH /auth/me`
Met à jour le profil public. **Protégée** (Bearer). Champs optionnels (`display_name`, `bio`, `avatar_url`) — ne renseigne que ceux à modifier.

**Body (JSON)** :
```json
{ "display_name": "Noelson", "bio": "Développeur", "avatar_url": "https://..." }
```

**Réponses** :
- `200` → `UserOut`
- `401` → non authentifié

```ts
const res = await fetch(`${BASE}/auth/me`, {
  method: "PATCH",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  },
  body: JSON.stringify({ display_name, bio, avatar_url }),
});
const user: UserOut = await res.json();
```

---

### `PATCH /auth/me/email`
Change l'email. **Protégée** (Bearer). Nécessite le **mot de passe actuel**.
Renvoie un **nouveau token** (le précédent devient invalide car le `sub` = email change).

**Body (JSON)** :
```json
{ "email": "nouveau@x.com", "password": "ancienMotDePasse" }
```

**Réponses** :
- `200` → `Token`
- `400` → `{ "detail": "Email already registered" }`
- `401` → `{ "detail": "Current password incorrect" }`

```ts
const res = await fetch(`${BASE}/auth/me/email`, {
  method: "PATCH",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  },
  body: JSON.stringify({ email, password }),
});
if (!res.ok) throw new Error((await res.json()).detail);
const { access_token } = (await res.json()) as Token; // remplace le token stocké
```

---

### `POST /auth/change-password`
Change le mot de passe. **Protégée** (Bearer). Nécessite le **mot de passe actuel**.
Le token existant reste valide (l'email ne change pas).

**Body (JSON)** :
```json
{ "current_password": "ancien", "new_password": "nouveauSecret123" }
```

**Réponses** :
- `200` → `{ "detail": "Password updated" }`
- `401` → `{ "detail": "Current password incorrect" }`

```ts
const res = await fetch(`${BASE}/auth/change-password`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  },
  body: JSON.stringify({ current_password, new_password }),
});
if (res.status === 401) throw new Error("Current password incorrect");
```

---

### `POST /posts`
Crée un article. **Protégée** (Bearer). L'`owner_id` est assigné automatiquement.

**Body (JSON)** :
```json
{ "title": "Mon post", "content": "Contenu...", "published": true }
```

**Réponses** :
- `201` → `PostOut`
- `401` → non authentifié

```ts
const res = await fetch(`${BASE}/posts`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  },
  body: JSON.stringify({ title, content, published: true }),
});
```

---

### `GET /posts`
Liste tous les articles. **Public**.

**Réponse** `200` → `PostOut[]`

```ts
const res = await fetch(`${BASE}/posts`);
const posts: PostOut[] = await res.json();
```

---

### `GET /posts/{post_id}`
Détail d'un article. **Public**.

**Réponses** :
- `200` → `PostOut`
- `404` → `{ "detail": "Post not found" }`

```ts
const res = await fetch(`${BASE}/posts/${id}`);
if (res.status === 404) throw new Error("Post not found");
const post: PostOut = await res.json();
```

---

### `DELETE /posts/{post_id}`
Supprime un article. **Protégée** (Bearer) — réservée au **propriétaire** du post.

**Headers** : `Authorization: Bearer <access_token>`

**Réponses** :
- `204` → supprimé (pas de corps)
- `401` → non authentifié
- `403` → `{ "detail": "Not enough permissions" }` (pas le propriétaire)
- `404` → post inexistant

```ts
const res = await fetch(`${BASE}/posts/${id}`, {
  method: "DELETE",
  headers: { Authorization: `Bearer ${token}` },
});
if (res.status === 403) throw new Error("Not enough permissions");
if (res.status === 404) throw new Error("Post not found");
```

---

## 4. Recommandations pour Next.js

- **Client API centralisé** : crée un helper `lib/api.ts` qui ajoute automatiquement le header
  `Authorization` et gère le `401` (redirection vers `/login`).
- **Stockage du token** : `localStorage` est simple mais vulnérable au XSS. Pour plus de sécurité,
  utilise un **cookie httpOnly** géré côté serveur (route handler / middleware Next.js).
- **Interception 401** : si `/auth/me` ou une route protégée répond `401`, efface le token et
  redirige vers la page de connexion.
- **CSRF** : avec des cookies, protège les requêtes mutantes (POST/DELETE) via un token CSRF ou
  l'en-tête `SameSite=Lax/Strict`.
- **Variables d'env** : expose la base URL via `NEXT_PUBLIC_API_URL` dans `.env.local`.

### Exemple de helper (`lib/api.ts`)

```ts
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }
  if (!res.ok) throw new Error((await res.json()).detail ?? "Erreur API");
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}
```
