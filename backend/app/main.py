"""NetZero — a Splitwise-style shared-expense app.

Backend entrypoint. Creates tables on startup, mounts the JSON API under /api,
and serves the no-build frontend as static files at the root.

Run from the backend/ directory:
    uvicorn app.main:app --reload
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .database import Base, engine
from . import models  # noqa: F401  (import registers models on Base)
from .routers import auth, groups, expenses, settlements, ml

Base.metadata.create_all(bind=engine)

app = FastAPI(title="NetZero API", version="1.0.0")

# Permissive CORS so you can run the frontend from a different origin during dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(expenses.router)
app.include_router(settlements.router)
app.include_router(ml.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---- serve the frontend ----
FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend",
)

if os.path.isdir(FRONTEND_DIR):
    # Serve index.html at / and static assets under their paths.
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
