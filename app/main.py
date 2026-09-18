"""
Trade Bridge — WhatsApp Delivery Bot
=====================================
Customer WhatsApp pe order ID bhejta hai -> bot MongoDB se status nikalta hai
-> AiSensy API se WhatsApp pe reply karta hai.

Endpoints:
  GET  /                    -> health check (Railway/Render isse ping karte hain)
  POST /webhook              -> AiSensy incoming-message webhook yahan aayega
  POST /admin/orders         -> naya order create/update karo (seller/admin use karega)
  GET  /admin/orders/{id}    -> ek order ka status dekho
"""

import os
import re
import logging

from fastapi import FastAPI, Request, HTTPException, Header
from pydantic import BaseModel

from app import db
from app.aisensy import send_whatsapp_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trade-bridge")

app = FastAPI(title="Trade Bridge - WhatsApp Delivery Bot")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")  # order update requests isse protect hote hain

# Order ID pattern — jaisa bhi format tum use karte ho usse yahan adjust kar lena.
# Abhi: 2-4 letters + 3-8 digits, jaise "TB12345" ya "AB1234567"
ORDER_ID_PATTERN = re.compile(r"\b([A-Z]{2,4}\d{3,8})\b", re.IGNORECASE)


# ─────────────────────────── health check ───────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "service": "trade-bridge-whatsapp-bot"}


# ─────────────────────────── incoming webhook ───────────────────────────

def extract_phone_and_text(payload: dict) -> tuple[str | None, str | None]:
    """
    AiSensy webhook payload se phone number aur message text nikalo.

    NOTE: AiSensy ka exact webhook payload shape tumhare account/setup pe depend
    kar sakta hai. Ye function common field names try karta hai. Agar match nahi
    ho raha, /webhook pe raw payload log ho raha hai (Railway logs me dekho) —
    us shape ke hisaab se neeche keys adjust kar dena.
    """
    # Common shapes to try
    phone = (
        payload.get("mobile")
        or payload.get("waId")
        or payload.get("from")
        or payload.get("sender")
        or payload.get("contact", {}).get("phone")
        or (payload.get("data") or {}).get("mobile")
    )
    text = (
        payload.get("text")
        or payload.get("message")
        or payload.get("body")
        or (payload.get("data") or {}).get("text")
    )

    # AiSensy kabhi-kabhi nested "messages" array bhejta hai (WhatsApp Cloud API jaisa)
    if not text and "messages" in payload:
        try:
            msg = payload["messages"][0]
            phone = phone or msg.get("from")
            text = msg.get("text", {}).get("body")
        except (KeyError, IndexError, TypeError):
            pass

    return phone, text


@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    logger.info(f"Incoming webhook payload: {payload}")

    phone, text = extract_phone_and_text(payload)

    if not phone or not text:
        logger.warning("Phone ya text extract nahi ho paya — payload shape check karo logs me.")
        return {"status": "ignored", "reason": "could not parse phone/text"}

    match = ORDER_ID_PATTERN.search(text)

    if not match:
        await send_whatsapp_message(
            phone,
            message="Please apna order ID bhejo (jaise TB12345) taaki main status bata sakoon.",
            template_params=["Please apna order ID bhejo (jaise TB12345) taaki main status bata sakoon."],
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

    await send_whatsapp_message(phone, message=reply_text, template_params=[reply_text])
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
