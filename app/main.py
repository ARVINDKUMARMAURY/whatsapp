"""
Trade Bridge — WhatsApp Delivery Bot (Evolution API / Baileys — FREE, unofficial)
===================================================================================
Customer WhatsApp pe order ID bhejta hai -> bot MongoDB se status nikalta hai
-> Evolution API (Baileys) se WhatsApp pe reply karta hai.

NOTE: Ye WhatsApp ka unofficial/reverse-engineered protocol use karta hai
(via Evolution API + Baileys). Pura free hai, koi 5-number test limit nahi,
lekin number ban hone ka risk hai — dedicated number use karo, primary nahi.

Endpoints:
  GET  /                    -> health check (Railway isse ping karega)
  POST /webhook               -> Evolution API se incoming events yahan aate hain
  POST /admin/orders          -> naya order create/update (seller/admin)
  GET  /admin/orders/{id}    -> ek order ka status dekho
"""

import os
import re
import csv
import io
import logging

from fastapi import FastAPI, Request, HTTPException, Header, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import db
from app.whatsapp import send_whatsapp_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trade-bridge")

app = FastAPI(title="Trade Bridge - WhatsApp Delivery Bot (Evolution API)")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# Order ID pattern — apna format alag hai to yahan adjust kar lena.
ORDER_ID_PATTERN = re.compile(r"\b([A-Z]{2,4}\d{3,8})\b", re.IGNORECASE)


# ─────────────────────────── health check ───────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "service": "trade-bridge-whatsapp-bot"}


@app.get("/admin/upload")
async def upload_page():
    """Drag-and-drop CSV upload UI — browser me kholo aur seedha CSV daalo."""
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    return FileResponse(os.path.join(static_dir, "admin.html"))


@app.get("/sample_orders.csv")
async def sample_csv():
    """Sample CSV template — upload page se download link ke liye."""
    root_dir = os.path.dirname(os.path.dirname(__file__))
    return FileResponse(os.path.join(root_dir, "sample_orders.csv"), filename="sample_orders.csv")


# ─────────────────────────── incoming messages ───────────────────────────

def extract_phone_and_text(payload: dict) -> tuple[str | None, str | None]:
    """
    Evolution API webhook shape (Baileys-based, event "messages.upsert"):
      {
        "event": "messages.upsert",
        "instance": "...",
        "data": {
          "key": {"remoteJid": "919876543210@s.whatsapp.net", "fromMe": false, ...},
          "message": {"conversation": "TB12345"}   # ya extendedTextMessage.text
        }
      }
    """
    try:
        data = payload.get("data", {})
        key = data.get("key", {})

        if key.get("fromMe"):
            return None, None  # apna hi bheja hua message, ignore karo (echo)

        remote_jid = key.get("remoteJid", "")
        phone = remote_jid.split("@")[0] if remote_jid else None

        msg = data.get("message", {}) or {}
        text = (
            msg.get("conversation")
            or msg.get("extendedTextMessage", {}).get("text")
            or msg.get("buttonsResponseMessage", {}).get("selectedDisplayText")
        )
        return phone, text
    except (AttributeError, TypeError):
        logger.warning(f"Payload parse nahi ho paya, raw: {payload}")
        return None, None


@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()

    # Sirf messages.upsert event process karo, baaki (connection updates,
    # presence, etc.) ignore karo
    event = payload.get("event", "")
    if event and event != "messages.upsert":
        return {"status": "ignored", "event": event}

    logger.info(f"Incoming webhook payload: {payload}")

    phone, text = extract_phone_and_text(payload)

    if not phone or not text:
        return {"status": "ignored"}

    match = ORDER_ID_PATTERN.search(text)

    if not match:
        await send_whatsapp_message(
            phone, "Please apna order ID bhejo (jaise TB12345) taaki main status bata sakoon."
        )
        return {"status": "ok", "reply": "asked_for_order_id"}

    order_id = match.group(1).upper()
    order = await db.get_order(order_id)

    if not order:
        reply_text = f"Order {order_id} nahi mila. Order ID check karke dobara bhejo."
    else:
        status = order.get("status", "Unknown")
        product = order.get("product", "")
        note = order.get("note", "")
        reply_text = f"Order {order_id} ({product}) ka status: {status}."
        if note:
            reply_text += f" Note: {note}"

    await send_whatsapp_message(phone, reply_text)
    return {"status": "ok", "reply": reply_text}


# ─────────────────────────── admin endpoints ───────────────────────────

class OrderIn(BaseModel):
    order_id: str
    phone: str
    product: str
    status: str
    note: str = ""


def check_admin(authorization: str | None):
    if not ADMIN_TOKEN:
        raise HTTPException(500, "ADMIN_TOKEN server pe set nahi hai — .env check karo.")
    if authorization != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(401, "Unauthorized — sahi admin token bhejo (Authorization: Bearer <token>)")


@app.post("/admin/orders")
async def create_or_update_order(order: OrderIn, authorization: str | None = Header(default=None)):
    check_admin(authorization)
    await db.upsert_order(order.order_id, order.phone, order.product, order.status, order.note)
    return {"status": "saved", "order_id": order.order_id.upper()}


@app.get("/admin/orders/{order_id}")
async def read_order(order_id: str, authorization: str | None = Header(default=None)):
    check_admin(authorization)
    order = await db.get_order(order_id)
    if not order:
        raise HTTPException(404, "Order nahi mila")
    order["_id"] = str(order["_id"])
    return order


class BulkOrdersIn(BaseModel):
    orders: list[OrderIn]


@app.post("/admin/orders/bulk")
async def bulk_create_orders(payload: BulkOrdersIn, authorization: str | None = Header(default=None)):
    """
    Ek saath bahut saare orders daalo — JSON array se.
    Example body: {"orders": [{"order_id": "TB1", "phone": "91...", "product": "...", "status": "Placed"}, ...]}
    """
    check_admin(authorization)
    orders_data = [o.model_dump() for o in payload.orders]
    result = await db.bulk_upsert_orders(orders_data)
    return result


@app.post("/admin/orders/bulk-csv")
async def bulk_create_orders_csv(
    file: UploadFile = File(...), authorization: str | None = Header(default=None)
):
    """
    CSV file upload karke ek saath saare orders daalo.
    CSV columns: order_id,phone,product,status,note (note optional)

    Example CSV:
        order_id,phone,product,status,note
        TB12345,919876543210,Wireless Mouse,Placed,
        TB12346,919876543211,Keyboard,Shipped,Expected in 2 days
    """
    check_admin(authorization)

    raw = await file.read()
    text = raw.decode("utf-8-sig")  # utf-8-sig Excel ke BOM ko bhi handle kar leta hai
    reader = csv.DictReader(io.StringIO(text))

    orders_data = [row for row in reader]
    if not orders_data:
        raise HTTPException(400, "CSV khali hai ya format sahi nahi hai")

    result = await db.bulk_upsert_orders(orders_data)
    return result
