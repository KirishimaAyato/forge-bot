"""
API сервер — раздаёт HTML и принимает/отдаёт данные из базы
Запускается вместе с ботом
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from database import Database

db = Database()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.init()
    yield
    # Shutdown (nothing to clean up for SQLite)

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_PATH = os.path.join(os.path.dirname(__file__), "webapp", "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def serve_webapp(user_id: int = 0):
    """Serve the WebApp HTML"""
    try:
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace(
            "/* __USER_ID_INJECT__ */",
            f"const TELEGRAM_USER_ID = {user_id};"
        )
        return HTMLResponse(content=html)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="WebApp HTML not found. Make sure webapp/index.html exists.")


@app.get("/api/state/{user_id}")
async def get_state(user_id: int):
    """WebApp loads state from here on startup"""
    state = await db.load_full_state(user_id)
    return JSONResponse(content=state)


@app.post("/api/state/{user_id}")
async def save_state(user_id: int, request: Request):
    """WebApp posts full state here on every save"""
    try:
        data = await request.json()
        await db.ensure_user(user_id, data.get("S", {}).get("name", "Воин"))
        await db.save_user_data(user_id, data)
        return JSONResponse(content={"ok": True})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
