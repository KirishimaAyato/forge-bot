"""
API сервер — раздаёт HTML и принимает/отдаёт данные из базы
Запускается вместе с ботом
"""
import json
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from database import Database

app = FastAPI()
db = Database()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Read the HTML file once at startup
HTML_PATH = os.path.join(os.path.dirname(__file__), "webapp", "index.html")


@app.on_event("startup")
async def startup():
    await db.init()


@app.get("/", response_class=HTMLResponse)
async def serve_webapp(user_id: int = 0):
    """Serve the WebApp HTML"""
    try:
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            html = f.read()
        # Inject user_id into the page
        html = html.replace(
            "/* __USER_ID_INJECT__ */",
            f"const TELEGRAM_USER_ID = {user_id};"
        )
        return HTMLResponse(content=html)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="WebApp HTML not found")


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


@app.get("/health")
async def health():
    return {"status": "ok"}
