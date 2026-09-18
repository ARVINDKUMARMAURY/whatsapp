"""
Meta WhatsApp Cloud API wrapper — DIRECT integration, koi paid BSP (AiSensy/
Gupshup/etc) nahi chahiye. Customer-initiated replies (service conversations)
free hain (24-hour window ke andar, Meta ka 1000/month free tier).

Setup (ek baar karna hai):
  1. https://developers.facebook.com pe Meta Developer account banao
  2. Ek "App" banao -> Product add karo -> WhatsApp
  3. Test number milega (ya apna business number verify karo)
  4. WhatsApp -> API Setup page se milega:
       - Temporary access token (24hr) -> Permanent token banane ke liye
         System User banao (Meta Business Suite -> Business Settings)
       - Phone Number ID
  5. Ye dono .env me daalo: WHATSAPP_TOKEN aur WHATSAPP_PHONE_NUMBER_ID
"""

import os
import httpx

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")

GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"


async def send_whatsapp_message(phone: str, message: str):
    """
    Customer ko WhatsApp pe seedha text message bhejo (Meta Cloud API).

    NOTE: Ye sirf tab free/allowed hai jab customer ne pehle khud message
    kiya ho aur 24 ghante ke andar reply ho raha ho ("service conversation").
    Agar tumhe khud se (customer ke message ke bina) message shuru karna hai,
    to Meta-approved template message chahiye hoga — wo doosra flow hai.
    """
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        raise RuntimeError(
            "WHATSAPP_TOKEN ya WHATSAPP_PHONE_NUMBER_ID set nahi hai — .env check karo."
        )

    digits = "".join(ch for ch in phone if ch.isdigit())

    payload = {
        "messaging_product": "whatsapp",
        "to": digits,
        "type": "text",
        "text": {"body": message},
    }
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(GRAPH_URL, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()
