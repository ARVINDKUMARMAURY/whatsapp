# Trade Bridge — WhatsApp Delivery Bot (100% Free — Meta Cloud API)

Customer WhatsApp pe apna order ID bhejta hai, bot MongoDB se status check karke
**seedha Meta ke WhatsApp Cloud API** se reply kar deta hai — koi paid BSP
(AiSensy/Gupshup/WATI) nahi, koi platform fee nahi.

## Ye free kyun hai

Meta WhatsApp Business API me har number ko **1000 free service conversations/month**
milte hain. "Service conversation" matlab: customer khud message kare, tum 24 ghante
ke andar reply karo. Yehi hamara use-case hai — customer order ID bhejta hai, bot
turant reply karta hai. Isliye koi BSP markup ya subscription fee ki zaroorat nahi.

(Agar tumhe khud se, bina customer ke message kiye, WhatsApp bhejna ho — jaise
"aapka order shipped ho gaya" proactive notification — us case me Meta-approved
template message chahiye hota hai, jiska bhi bahut hi sasta per-message rate hai.
Filhal is bot me sirf reply flow banaya hai jo poora free hai.)

## Kaise kaam karta hai

```
Customer (WhatsApp) --order ID--> Meta Cloud API --webhook--> ye bot --> MongoDB lookup
                                                                    |
                                                                    v
Customer (WhatsApp) <--status reply-- Meta Cloud API <--API call--+
```

## Setup — Step by Step

### 1. Meta Developer account + App banao

1. https://developers.facebook.com pe jao, login/signup karo
2. "My Apps" -> "Create App" -> type: **Business**
3. App ke andar "Add Product" -> **WhatsApp** select karo
4. WhatsApp -> **API Setup** page pe tumhe milega:
   - Ek **test phone number** (free, turant use kar sakte ho testing ke liye)
   - **Temporary access token** (24 ghante valid — permanent banana neeche step 2 me)
   - **Phone Number ID** (copy kar lo, `.env` me daalna hai)

### 2. Permanent access token banao (temporary token 24hr me expire ho jata hai)

1. Meta Business Suite -> Business Settings -> Users -> **System Users**
2. Naya System User banao (Admin role)
3. Us user ko apne WhatsApp app se assign karo
4. "Generate Token" -> apna app select karo -> permissions me
   `whatsapp_business_messaging` aur `whatsapp_business_management` check karo
5. Ye permanent token `.env` me `WHATSAPP_TOKEN` me daalo

### 3. Dependencies + environment

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env` me bharo:
- `MONGO_URI` — MongoDB Atlas free tier connection string
- `WHATSAPP_TOKEN` — permanent token (step 2)
- `WHATSAPP_PHONE_NUMBER_ID` — step 1 se
- `VERIFY_TOKEN` — koi bhi random string khud bana lo (webhook verify ke liye)
- `ADMIN_TOKEN` — koi bhi random strong string (admin API protect karne ke liye)

### 4. Local run (test ke liye)

```bash
uvicorn app.main:app --reload
```

### 5. Railway pe deploy

1. Naya Railway project -> GitHub repo connect karo
2. Saare `.env.example` wale variables Railway dashboard me daalo
3. Deploy hone ke baad URL milega: `https://xxx.up.railway.app`

### 6. Webhook Meta me configure karo

1. Meta App Dashboard -> WhatsApp -> **Configuration**
2. Callback URL: `https://xxx.up.railway.app/webhook`
3. Verify Token: wahi jo `.env` me `VERIFY_TOKEN` daala tha
4. "Verify and Save" click karo — agar sab sahi hai to turant verify ho jayega
5. **Webhook fields** me `messages` subscribe karo (zaroor karna, warna incoming
   messages nahi aayenge)

### 7. Test karo

Apne WhatsApp se test number pe koi order ID bhejo (jaise `TB12345`) — pehle
neeche diya admin API se ek test order bana lo.

## Order add/update karna (admin)

```bash
curl -X POST https://xxx.up.railway.app/admin/orders \
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

Status check:

```bash
curl https://xxx.up.railway.app/admin/orders/TB12345 \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

## Important limits (free tier)

- Test phone number sirf **5 pre-approved recipient numbers** ko message kar sakta
  hai jab tak business verification complete nahi karte
- Production me apna khud ka business number add karna hoga (verification lagta hai,
  free hai, kuch din lag sakte hain Meta approval me)
- 1000 free service conversations/month per phone number — is scale ke liye kaafi hai

## Order ID format badalna

`app/main.py` me `ORDER_ID_PATTERN` regex hai (`2-4 letters + 3-8 digits`, jaise
`TB12345`). Apna format alag hai to yahan adjust kar dena.

## Files

| File | Kaam |
|---|---|
| `app/main.py` | FastAPI app — webhook + admin endpoints |
| `app/db.py` | MongoDB connection aur order queries |
| `app/whatsapp.py` | Meta WhatsApp Cloud API se message bhejna |
| `Procfile` | Railway deployment config |
| `.env.example` | Environment variables template |
