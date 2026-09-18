"""
Trade Bridge — WhatsApp Delivery Bot (Meta Cloud API — FREE, no BSP)
=====================================================================
Customer WhatsApp pe order ID bhejta hai -> bot MongoDB se status nikalta hai
-> Meta WhatsApp Cloud API se seedha WhatsApp pe reply karta hai.

Ye paid BSP (AiSensy/Gupshup) use nahi karta — seedha Meta ka official Cloud
API hai. Customer-initiated replies (24hr window ke andar) free hain.

Endpoints:
  GET  /                    -> health check (Railway isse ping karega)
  GET  /webhook              -> Meta webhook verification (setup ke time pe)
  POST /webhook               -> incoming WhatsApp messages yahan aate hain
  POST /admin/orders          -> naya order create/update (seller/admin)
  GET  /admin/orders/{id}    -> ek order ka status dekho
"""

import os
import re
import logging

from fastapi import FastAPI, Request, HTTPException, Header, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app import db
from app.whatsapp import send_whatsapp_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trade-bridge")

app = FastAPI(title="Trade Bridge - WhatsApp Delivery Bot")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")  # Meta webhook verify ke liye, khud choose karo

# Order ID pattern — apna format alag hai to yahan adjust kar lena.
# Abhi: 2-4 letters + 3-8 digits, jaise "TB12345"
ORDER_ID_PATTERN = re.compile(r"\b([A-Z]{2,4}\d{3,8})\b", re.IGNORECASE)


# ─────────────────────────── health check ───────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "service": "trade-bridge-whatsapp-bot"}


# ─────────────────────── webhook verification (Meta setup) ───────────────────────

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
):
    """
    Meta jab webhook URL configure karte waqt ek GET request bhejta hai verify
    karne ke liye. VERIFY_TOKEN wahi hona chahiye jo tum Meta dashboard me
    daaloge webhook setup karte waqt.
    """
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully by Meta.")
        return PlainTextResponse(hub_challenge)
    raise HTTPException(403, "Verification failed — VERIFY_TOKEN match nahi hua.")


# ─────────────────────────── incoming messages ───────────────────────────

def extract_phone_and_text(payload: dict) -> tuple[str | None, str | None]:
    """
    Meta ka webhook payload shape fixed hai (WhatsApp Cloud API docs):
    entry[0].changes[0].value.messages[0]
    """
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        messages = value.get("messages")
        if not messages:
            return None, None  # status update / read-receipt webhook, message nahi
        msg = messages[0]
        phone = msg.get("from")
        text = msg.get("text", {}).get("body")
        return phone, text
    except (KeyError, IndexError, TypeError):
        logger.warning(f"Payload parse nahi ho paya, raw: {payload}")
        return None, None


@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    logger.info(f"Incoming webhook payload: {payload}")

    phone, text = extract_phone_and_text(payload)

    if not phone or not text:
        # Ye normal hai — Meta status updates (delivered/read) bhi isi endpoint
        # pe bhejta hai, unme "messages" nahi "statuses" hota hai. Ignore karo.
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
