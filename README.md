# Trade Bridge — WhatsApp Delivery Bot (100% Free — Evolution API / Baileys)

Customer WhatsApp pe apna order ID bhejta hai, bot MongoDB se status check karke
WhatsApp pe reply kar deta hai — **Evolution API** (open-source, Baileys library
pe based) use karke. Koi Meta approval nahi, koi paid BSP nahi, koi per-message
fee nahi — poora free aur unlimited.

## ⚠️ Important — pehle ye samjho

Ye **unofficial** WhatsApp connection hai — Meta ka official Business API nahi.
Evolution API, WhatsApp Web ke protocol ko reverse-engineer karke (Baileys library
ke through) kaam karta hai, bilkul waise jaise tum browser me WhatsApp Web use
karte ho.

**Risks:**
- WhatsApp inhe detect karke number **ban** kar sakta hai (kabhi bhi, koi warning
  nahi milegi zaroori nahi)
- **Apna personal/primary number kabhi mat use karna.** Ek alag dedicated
  number rakho jise ban hone pe replace kar sako
- Naye number pe automation turant shuru mat karo — pehle kuch din normal
  WhatsApp jaisa use karo (thoda manual chat karo), phir gradually automate karo
- High volume (jaise 100+ messages/day) pe ban ka chance badh jata hai

Agar ye business-critical hai (real customers, real revenue), to safer option
Meta ka official Cloud API hai (maine pehle wo bhi bana diya tha — free bhi hai
is use-case ke liye, bas thoda setup zyada hai). Ye Evolution API route sirf
tab lena jab risk acceptable ho.

## Architecture

```
Customer (WhatsApp) --order ID--> Evolution API (Baileys) --webhook--> ye bot
                                                                   |
                                                                   v
                                                          MongoDB lookup
                                                                   |
Customer (WhatsApp) <--status reply-- Evolution API <--REST call--+
```

Do services chahiye:
1. **Evolution API** — WhatsApp se connect karta hai (Docker image, Railway pe deploy)
2. **Ye bot** (Trade Bridge) — order logic + MongoDB (isi repo ka code)

## Setup — Step by Step

### 1. Evolution API deploy karo (Railway pe alag service)

1. Railway me naya project banao
2. "Deploy from Docker Image" choose karo, image daalo: `atendai/evolution-api:latest`
3. Environment variables set karo:
   ```
   AUTHENTICATION_API_KEY=koi_bhi_strong_random_string
   DATABASE_ENABLED=false
   ```
   (production ke liye DB enable karna better hai session persist rehne ke liye,
   lekin simple start ke liye DATABASE_ENABLED=false chalega)
4. Deploy hone ke baad URL milega: `https://your-evolution-api.up.railway.app`
5. Isi URL ko is bot ke `.env` me `EVOLUTION_API_URL` me daalna hai

### 2. WhatsApp instance banao aur QR scan karo

```bash
curl -X POST https://your-evolution-api.up.railway.app/instance/create \
  -H "apikey: <AUTHENTICATION_API_KEY jo upar set kiya>" \
  -H "Content-Type: application/json" \
  -d '{
    "instanceName": "tradebridge",
    "qrcode": true,
    "webhook": {
      "url": "https://your-trade-bridge-bot.up.railway.app/webhook",
      "events": ["MESSAGES_UPSERT"]
    }
  }'
```

Response me QR code (base64 image) milega — usse browser me open karke apne
**dedicated WhatsApp number** se scan karo (WhatsApp -> Linked Devices -> Link a Device).

Connection status check karne ke liye:
```bash
curl https://your-evolution-api.up.railway.app/instance/connectionState/tradebridge \
  -H "apikey: <AUTHENTICATION_API_KEY>"
```

### 3. Is bot (Trade Bridge) ko deploy karo

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env` me bharo:
- `MONGO_URI` — MongoDB Atlas free tier
- `EVOLUTION_API_URL` — step 1 ka URL
- `EVOLUTION_API_KEY` — step 1 me set kiya `AUTHENTICATION_API_KEY`
- `EVOLUTION_INSTANCE` — `tradebridge` (ya jo naam diya step 2 me)
- `ADMIN_TOKEN` — koi bhi random strong string

Railway pe deploy karo (naya project, ye repo connect karo, saare env vars daalo).

### 4. Test karo

Dedicated number pe koi aur WhatsApp se order ID bhejo (jaise `TB12345`) — pehle
neeche diya admin API se test order bana lo.

## Order add/update karna (admin)

```bash
curl -X POST https://your-trade-bridge-bot.up.railway.app/admin/orders \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "TB12345",
    "phone": "919876543210",
    "product": "Wireless Mouse",
    "status": "Shipped",
    "note": "Expected delivery in 2 days"
  }'
```

## Saare orders ek saath daalna (Bulk Import)

Ek-ek order curl se daalna practical nahi hai — isliye do bulk options hain:

## Saare orders ek saath daalna (Bulk Import)

### Option A: Drag-and-drop web page (sabse aasaan, koi command nahi)

Browser me kholo: `https://your-trade-bridge-bot.up.railway.app/admin/upload`

- Server URL (auto-filled) aur apna `ADMIN_TOKEN` bharo
- CSV file drag-drop karo (ya click karke choose karo)
- "Upload Orders" click karo — kitne save hue, kitne fail hue turant dikh jayega
- Page pe hi sample CSV template download karne ka link hai

### Option B: CSV file se (curl se, agar terminal se karna ho)

`sample_orders.csv` jaisi file banao (columns: `order_id,phone,product,status,note`
— `note` optional hai). Excel/Google Sheets me table banao, "Export as CSV" karo,
phir:

```bash
curl -X POST https://your-trade-bridge-bot.up.railway.app/admin/orders/bulk-csv \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -F "file=@orders.csv"
```

Response me batayega kitne successfully add hue aur kitne fail hue (aur kyun).

### Option C: JSON array se (agar data kahin script/API se aa raha ho)

```bash
curl -X POST https://your-trade-bridge-bot.up.railway.app/admin/orders/bulk \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "orders": [
      {"order_id": "TB12345", "phone": "919876543210", "product": "Wireless Mouse", "status": "Placed"},
      {"order_id": "TB12346", "phone": "919876543211", "product": "Keyboard", "status": "Shipped", "note": "Expected in 2 days"}
    ]
  }'
```

Dono endpoints **upsert** karte hain — matlab agar `order_id` already exist karta
hai to update ho jayega, naya hai to create ho jayega. Same file/list dobara bhej
sakte ho status update karne ke liye (jaise sab "Shipped" se "Delivered" karna ho).

## Evolution API payload format note

Evolution API ka `/message/sendText` payload shape version ke hisaab se thoda
badalta rehta hai (`{"number","text"}` vs `{"number","textMessage":{"text"}}`).
`app/whatsapp.py` dono try karta hai automatically. Agar phir bhi error aaye,
apne deployed Evolution API ke `/docs` (Swagger) endpoint pe exact schema check
kar lena.

## Order ID format badalna

`app/main.py` me `ORDER_ID_PATTERN` regex hai (`2-4 letters + 3-8 digits`, jaise
`TB12345`). Apna format alag hai to yahan adjust kar dena.

## Files

| File | Kaam |
|---|---|
| `app/main.py` | FastAPI app — webhook + admin endpoints |
| `app/db.py` | MongoDB connection aur order queries |
| `app/whatsapp.py` | Evolution API (Baileys) se message bhejna |
| `Procfile` | Railway deployment config (is bot ke liye) |
| `.env.example` | Environment variables template |
