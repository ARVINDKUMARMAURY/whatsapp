# Trade Bridge — WhatsApp Delivery Bot

Customer WhatsApp pe apna order ID bhejta hai, bot MongoDB se status check karke
AiSensy API ke through WhatsApp pe reply kar deta hai.

## Kaise kaam karta hai

```
Customer (WhatsApp) --order ID--> AiSensy --webhook--> ye bot --> MongoDB lookup
                                                            |
                                                            v
Customer (WhatsApp) <--status reply-- AiSensy <--API call--+
```

## Setup

### 1. Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment variables

`.env.example` ko `.env` me copy karo aur values bharo:

```bash
cp .env.example .env
```

- `MONGO_URI` — tumhara MongoDB connection string (Atlas free tier chal jayega)
- `AISENSY_API_KEY` — AiSensy Dashboard → Manage → API Key
- `AISENSY_CAMPAIGN_NAME` — AiSensy → Campaigns me jo API campaign banaya hai uska exact naam
- `COUNTRY_CODE` — default 91 (India)
- `ADMIN_TOKEN` — koi bhi random strong string, admin endpoints protect karne ke liye

### 3. Local run

```bash
uvicorn app.main:app --reload
```

`http://localhost:8000` pe health check milega.

## AiSensy webhook setup

1. AiSensy Dashboard me apna server ka webhook URL set karo: `https://your-app.up.railway.app/webhook`
2. Ek WhatsApp template banao jisme sirf ek variable ho `{{1}}` (jisme poora reply text jayega) — 
   simplest approach hai, baad me multi-variable template bhi bana sakte ho
3. **Important:** AiSensy ka incoming-message webhook payload format account-wise thoda
   different ho sakta hai. Pehli baar test message bhejo aur Railway logs me dekho
   (`logger.info` se poora payload print hota hai) — agar bot phone/text extract nahi
   kar pa raha, `app/main.py` ke `extract_phone_and_text()` function me field names
   adjust kar dena us actual payload shape ke hisaab se.

## Order add/update karna (admin)

Naya order banane ya status update karne ke liye:

```bash
curl -X POST https://your-app.up.railway.app/admin/orders \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "TB12345",
    "phone": "9876543210",
    "product": "Wireless Mouse",
    "status": "Shipped",
    "note": "Expected delivery in 2 days"
  }'
```

Status check karne ke liye:

```bash
curl https://your-app.up.railway.app/admin/orders/TB12345 \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

## Railway pe deploy

1. Naya Railway project banao, ye GitHub repo connect karo
2. Environment variables Railway dashboard me set karo (`.env.example` wale saare)
3. Railway automatically `Procfile` use karke deploy kar dega
4. Deploy hone ke baad jo URL milega (`https://xxx.up.railway.app`), wahi:
   - AiSensy webhook me daalo (`/webhook` path ke saath)
   - Trade Bridge config screen me "Server URL" field me bhi wahi daalo

## Order ID format badalna

Abhi `app/main.py` me `ORDER_ID_PATTERN` regex hai jo `2-4 letters + 3-8 digits`
(jaise `TB12345`) match karta hai. Apna format alag hai to yahan regex adjust kar dena.

## Files

| File | Kaam |
|---|---|
| `app/main.py` | FastAPI app — webhook handler + admin endpoints |
| `app/db.py` | MongoDB connection aur order queries |
| `app/aisensy.py` | AiSensy API se WhatsApp message bhejna |
| `Procfile` | Railway deployment config |
| `.env.example` | Environment variables ka template |
