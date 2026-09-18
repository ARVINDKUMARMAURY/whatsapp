"""
Evolution API wrapper — Baileys library pe based, self-hosted, unofficial
WhatsApp connection (WhatsApp Web jaisa QR-scan se connect hota hai).

PURA FREE hai, koi Meta approval/BSP fee nahi lagta. Lekin ye WhatsApp ka
official API nahi hai — reverse-engineered WhatsApp Web protocol use karta
hai, isliye number ban hone ka risk hai. Kabhi apna primary number isme mat
lagana — alag dedicated number use karo.

Setup:
  1. Evolution API ko Railway pe alag service ki tarah deploy karo
     (Docker image: atendai/evolution-api) — README me poora process hai
  2. Ek "instance" banao (= ek WhatsApp connection/session)
  3. QR code scan karo apne dedicated WhatsApp number se
  4. Evolution API URL + API key + instance name .env me daalo
"""

import os
import httpx

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "")


async def send_whatsapp_message(phone: str, message: str):
    """
    Customer ko WhatsApp text message bhejo, Evolution API (Baileys) ke through.
    """
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY or not EVOLUTION_INSTANCE:
        raise RuntimeError(
            "EVOLUTION_API_URL / EVOLUTION_API_KEY / EVOLUTION_INSTANCE set nahi hai — .env check karo."
        )

    digits = "".join(ch for ch in phone if ch.isdigit())

    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {"number": digits, "text": message}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            # Evolution API ka payload shape version-wise thoda badal sakta hai
            # (kuch versions "textMessage": {"text": ...} expect karte hain).
            # Agar upar wala fail ho raha hai, retry with nested shape:
            fallback_payload = {"number": digits, "textMessage": {"text": message}}
            resp = await client.post(url, json=fallback_payload, headers=headers)
        resp.raise_for_status()
        return resp.json()
