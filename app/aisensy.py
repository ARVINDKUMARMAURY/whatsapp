"""
AiSensy Official API wrapper — WhatsApp pe message bhejne ke liye.

AiSensy campaign-based sending API use karta hai:
  POST https://backend.aisensy.com/campaign/t1/api/v2

Docs: AiSensy Dashboard -> Manage -> API Key
"""

import os
import httpx

AISENSY_API_KEY = os.getenv("AISENSY_API_KEY", "")
AISENSY_CAMPAIGN_NAME = os.getenv("AISENSY_CAMPAIGN_NAME", "")
COUNTRY_CODE = os.getenv("COUNTRY_CODE", "91")

AISENSY_URL = "https://backend.aisensy.com/campaign/t1/api/v2"


async def send_whatsapp_message(phone: str, message: str, template_params: list[str] | None = None):
    """
    Customer ko WhatsApp message bhejo AiSensy campaign ke through.

    phone: 10-digit number (bina country code ke) ya poora number — dono handle karte hain.
    message: sirf logging/fallback ke liye — actual content template_params se aata hai
             kyunki AiSensy pre-approved templates use karta hai.
    template_params: tumhare AiSensy template ke {{1}}, {{2}}... variables, order me.
    """
    if not AISENSY_API_KEY or not AISENSY_CAMPAIGN_NAME:
        raise RuntimeError(
            "AISENSY_API_KEY ya AISENSY_CAMPAIGN_NAME set nahi hai — .env check karo."
        )

    # phone number normalize karo: sirf digits, country code ke saath
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 10:
        destination = f"{COUNTRY_CODE}{digits}"
    else:
        destination = digits  # already country code included maan lo

    payload = {
        "apiKey": AISENSY_API_KEY,
        "campaignName": AISENSY_CAMPAIGN_NAME,
        "destination": destination,
        "userName": "Trade Bridge Customer",
        "templateParams": template_params or [message],
        "source": "trade-bridge-bot",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(AISENSY_URL, json=payload)
        resp.raise_for_status()
        return resp.json()
