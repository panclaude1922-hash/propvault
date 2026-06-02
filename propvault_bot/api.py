"""
api.py — FastAPI сервер
Эндпоинты:
  POST /auth          — проверка initData от Telegram, возврат роли
  GET  /properties    — список одобренных объектов
  GET  /properties/:id — один объект
  GET  /realtor/me    — профиль риелтора (подписка, объекты)
"""

import hashlib
import hmac
import json
import time
from urllib.parse import unquote, parse_qsl

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import BOT_TOKEN
from database import (
    get_user, create_user,
    get_active_subscription,
    get_realtor_properties,
    get_property,
    PLAN_LABELS, PLAN_LIMITS
)

app = FastAPI(title="PropVault API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── helpers ──────────────────────────────────────────────

def verify_telegram_init_data(init_data: str) -> dict:
    """
    Проверяет подпись initData от Telegram WebApp.
    Возвращает распарсенные данные или кидает исключение.
    """
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise ValueError("hash отсутствует")

    # Проверка актуальности (не старше 24 часов)
    auth_date = int(parsed.get("auth_date", 0))
    if time.time() - auth_date > 86400:
        raise ValueError("initData устарел")

    # Формируем data-check-string
    data_check = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )

    # Считаем HMAC
    secret_key = hmac.new(
        b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    expected_hash = hmac.new(
        secret_key, data_check.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("Неверная подпись")

    # Парсим user
    user_str = parsed.get("user", "{}")
    parsed["user"] = json.loads(user_str)
    return parsed


# ── schemas ──────────────────────────────────────────────

class AuthRequest(BaseModel):
    init_data: str


# ── routes ───────────────────────────────────────────────

@app.post("/auth")
async def auth(body: AuthRequest):
    """
    Принимает initData от Telegram WebApp.
    Создаёт пользователя если новый.
    Возвращает роль, подписку и флаги доступа.
    """
    try:
        data = verify_telegram_init_data(body.init_data)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    tg_user = data["user"]
    tg_id = tg_user["id"]

    # Получаем или создаём пользователя
    user = await get_user(tg_id)
    if not user:
        await create_user(
            tg_id,
            tg_user.get("username"),
            tg_user.get("first_name", "") + " " + tg_user.get("last_name", ""),
            role="investor"
        )
        user = await get_user(tg_id)

    role = user["role"]
    response = {
        "tg_id": tg_id,
        "role": role,
        "first_name": tg_user.get("first_name", ""),
        "username": tg_user.get("username"),
        "subscription": None,
        "can_add_property": False,
        "properties_left": 0,
    }

    if role == "realtor":
        sub = await get_active_subscription(tg_id)
        if sub:
            plan = sub["plan"]
            count_props = len(await get_realtor_properties(tg_id))
            limit = PLAN_LIMITS[plan]
            response["subscription"] = {
                "plan": plan,
                "label": PLAN_LABELS[plan],
                "expires_at": sub["expires_at"][:10],
                "properties_used": count_props,
                "properties_limit": limit if limit < 9999 else None,
            }
            response["can_add_property"] = count_props < limit
            response["properties_left"] = max(0, limit - count_props) if limit < 9999 else 999

    return response


@app.get("/properties")
async def list_properties(
    city: str = None,
    min_yield: float = None,
    limit: int = 20,
    offset: int = 0
):
    """Список опубликованных объектов с фильтрацией."""
    import aiosqlite
    from database import DB_PATH

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        sql = """
            SELECT p.*, u.full_name as realtor_name
            FROM properties p
            JOIN users u ON p.realtor_id = u.tg_id
            WHERE p.status = 'approved'
        """
        params = []

        if city:
            sql += " AND (p.city LIKE ? OR p.region LIKE ?)"
            params += [f"%{city}%", f"%{city}%"]

        if min_yield:
            sql += " AND p.yield_pct >= ?"
            params.append(min_yield)

        sql += " ORDER BY p.approved_at DESC LIMIT ? OFFSET ?"
        params += [limit, offset]

        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
            props = [dict(r) for r in rows]

    return {"items": props, "total": len(props), "offset": offset}


@app.get("/properties/{prop_id}")
async def get_property_detail(prop_id: int):
    """Детальная информация об объекте."""
    prop = await get_property(prop_id)
    if not prop or prop["status"] != "approved":
        raise HTTPException(status_code=404, detail="Объект не найден")
    return prop


@app.get("/realtor/properties")
async def realtor_properties(x_tg_init_data: str = Header(None)):
    """Объекты конкретного риелтора (требует авторизации)."""
    if not x_tg_init_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    try:
        data = verify_telegram_init_data(x_tg_init_data)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    tg_id = data["user"]["id"]
    user = await get_user(tg_id)
    if not user or user["role"] != "realtor":
        raise HTTPException(status_code=403, detail="Только для риелторов")

    props = await get_realtor_properties(tg_id)
    return {"items": props}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "PropVault API"}
