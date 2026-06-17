# Deployment

## Backend

```bash
cd services/api
python tests/run_mvp.py
uvicorn app.main:app --reload
```

## Docker Compose

```bash
cd infra
docker compose up --build
```

## Frontend

```bash
npm install
npm --workspace apps/admin-web run dev
```

## Desktop

```bash
npm install
npm --workspace apps/desktop run dev
```

The current environment showed pytest hanging in the plugin/runner layer, while direct FastAPI `TestClient` calls and the direct MVP runner succeeded. Use `python tests/run_mvp.py` until the local pytest environment is cleaned up.
