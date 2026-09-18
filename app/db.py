"""
MongoDB connection aur orders collection ke saath kaam karne wale functions.
"""

import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "tradebridge")

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
orders_col = db["orders"]
users_col = db["users"]  # phone number -> conversation state (agar future me chahiye)


async def get_order(order_id: str):
    """Order ID se order dhoondo (case-insensitive)."""
    return await orders_col.find_one({"order_id": order_id.strip().upper()})


async def get_orders_by_phone(phone: str):
    """Kisi customer ke saare orders (latest pehle)."""
    cursor = orders_col.find({"phone": phone}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def upsert_order(order_id: str, phone: str, product: str, status: str, note: str = ""):
    """
    Naya order banao ya existing update karo. Admin panel / seller isse call karega
    jab order create ho ya status change ho (e.g. "Placed" -> "Shipped" -> "Delivered").
    """
    now = datetime.now(timezone.utc)
    result = await orders_col.update_one(
        {"order_id": order_id.strip().upper()},
        {
            "$set": {
                "phone": phone,
                "product": product,
                "status": status,
                "note": note,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return result


async def update_status(order_id: str, status: str, note: str = ""):
    """Sirf status update karna ho to isse use karo (order pehle se exist karna chahiye)."""
    result = await orders_col.update_one(
        {"order_id": order_id.strip().upper()},
        {"$set": {"status": status, "note": note, "updated_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


async def bulk_upsert_orders(orders: list[dict]):
    """
    Ek saath bahut saare orders create/update karo. Har dict me kam se kam
    order_id, phone, product, status honi chahiye (note optional).

    Return: {"success": count, "failed": [{"row": i, "error": "..."}]}
    """
    now = datetime.now(timezone.utc)
    success = 0
    failed = []

    for i, o in enumerate(orders):
        try:
            order_id = str(o["order_id"]).strip().upper()
            phone = str(o["phone"]).strip()
            product = str(o.get("product", "")).strip()
            status = str(o.get("status", "Placed")).strip()
            note = str(o.get("note", "")).strip()

            if not order_id or not phone:
                raise ValueError("order_id aur phone dono zaroori hain")

            await orders_col.update_one(
                {"order_id": order_id},
                {
                    "$set": {
                        "phone": phone,
                        "product": product,
                        "status": status,
                        "note": note,
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            success += 1
        except (KeyError, ValueError) as e:
            failed.append({"row": i, "error": str(e), "data": o})

    return {"success": success, "failed": failed}
