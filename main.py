import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
import jwt
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import MenuItem, Reservation, Order, Review


JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGO = "HS256"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@kokumandcoast.in")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


app = FastAPI(title="Kokum & Coast API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Helpers ----------
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def oid(obj: Any) -> str:
    if isinstance(obj, ObjectId):
        return str(obj)
    return str(obj)


def serialize_doc(doc: Dict) -> Dict:
    if not doc:
        return doc
    out = {**doc}
    if "_id" in out:
        out["id"] = oid(out.pop("_id"))
    # convert datetimes
    for k, v in list(out.items()):
        if isinstance(v, (datetime,)):
            out[k] = v.isoformat()
    return out


def create_jwt(email: str) -> str:
    payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=8),
        "iat": datetime.now(timezone.utc),
        "role": "admin",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


bearer = HTTPBearer(auto_error=False)


def require_admin(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing credentials")
    token = creds.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Forbidden")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------- Basic & Info ----------
@app.get("/")
def root():
    return {"message": "Kokum & Coast API running"}


@app.get("/api/info")
def get_info():
    return {
        "name": "Kokum & Coast – Coastal Maharashtra, Reimagined",
        "address": "Shop No. 12, Colaba Causeway, Colaba, Mumbai 400005",
        "phone": "+91-22-4000-1234",
        "email": "hello@kokumandcoast.in",
        "hours": {
            "mon": "11:00–23:00",
            "tue": "11:00–23:00",
            "wed": "11:00–23:00",
            "thu": "11:00–23:00",
            "fri": "11:00–23:30",
            "sat": "09:00–23:30",
            "sun": "09:00–22:30",
        },
        "socials": {
            "instagram": "https://instagram.com/kokumandcoast",
            "facebook": "https://facebook.com/kokumandcoast",
            "twitter": "https://twitter.com/kokumandcoast",
        },
    }


# ---------- Auth ----------
class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    if req.email.lower() == ADMIN_EMAIL.lower() and req.password == ADMIN_PASSWORD:
        token = create_jwt(req.email)
        return TokenResponse(access_token=token)
    raise HTTPException(status_code=401, detail="Invalid credentials")


# ---------- Menu ----------
@app.get("/api/menu")
def list_menu(category: Optional[str] = None):
    query: Dict = {}
    if category:
        query["category"] = category
    items = db["menuitem"].find(query).sort("name", 1)
    return [serialize_doc(i) for i in items]


@app.post("/api/menu", dependencies=[Depends(require_admin)])
def create_menu_item(item: MenuItem):
    _id = db["menuitem"].insert_one({**item.model_dump(), "created_at": datetime.now(timezone.utc)}).inserted_id
    return {"id": oid(_id)}


@app.delete("/api/menu/{item_id}", dependencies=[Depends(require_admin)])
def delete_menu_item(item_id: str):
    res = db["menuitem"].delete_one({"_id": ObjectId(item_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"ok": True}


@app.post("/api/menu/seed", dependencies=[Depends(require_admin)])
def seed_menu():
    if db["menuitem"].count_documents({}) > 0:
        return {"message": "Menu already seeded"}
    sample = [
        {"name": "Goan Prawn Croquette", "category": "Starters", "description": "Crisp prawn bites with kokum aioli", "price": 420, "veg": False, "spicy_level": 2, "tags": ["goan", "prawn"]},
        {"name": "Kokum Fish Curry", "category": "Mains", "description": "Tangy kokum-based curry, fresh catch of the day", "price": 590, "veg": False, "spicy_level": 3, "tags": ["kokum", "malvani"]},
        {"name": "Mumbai Biryani", "category": "Mains", "description": "City-style fragrant biryani with raita", "price": 520, "veg": False, "spicy_level": 2, "tags": ["biryani"]},
        {"name": "Sol Kadhi", "category": "Beverages", "description": "Refreshing kokum-coconut cooler", "price": 180, "veg": True, "spicy_level": 0, "tags": ["kokum", "refresh"]},
        {"name": "Puran Poli", "category": "Desserts", "description": "Classic sweet flatbread with ghee", "price": 260, "veg": True, "spicy_level": 0, "tags": ["maharashtrian"]},
        {"name": "Masala Chai", "category": "Beverages", "description": "Spiced tea the Mumbai way", "price": 120, "veg": True, "spicy_level": 0, "tags": ["chai"]},
    ]
    for it in sample:
        db["menuitem"].insert_one({**it, "created_at": datetime.now(timezone.utc)})
    return {"inserted": len(sample)}


# ---------- Reservations ----------
@app.post("/api/reservations")
def create_reservation(data: Reservation):
    _id = db["reservation"].insert_one({**data.model_dump(), "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}).inserted_id
    return {"id": oid(_id), "status": "pending"}


@app.get("/api/reservations", dependencies=[Depends(require_admin)])
def list_reservations(limit: int = 100):
    rows = db["reservation"].find({}).sort("created_at", -1).limit(limit)
    return [serialize_doc(r) for r in rows]


class ReservationStatus(BaseModel):
    status: str


@app.patch("/api/reservations/{res_id}", dependencies=[Depends(require_admin)])
def update_reservation_status(res_id: str, body: ReservationStatus):
    res = db["reservation"].update_one({"_id": ObjectId(res_id)}, {"$set": {"status": body.status, "updated_at": datetime.now(timezone.utc)}})
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"ok": True}


# ---------- Orders ----------
@app.post("/api/orders")
def create_order(order: Order):
    payload = {**order.model_dump(), "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}
    _id = db["order"].insert_one(payload).inserted_id
    return {"id": oid(_id), "status": order.status}


@app.get("/api/orders", dependencies=[Depends(require_admin)])
def list_orders(limit: int = 100):
    rows = db["order"].find({}).sort("created_at", -1).limit(limit)
    return [serialize_doc(r) for r in rows]


class OrderStatus(BaseModel):
    status: str
    payment_status: Optional[str] = None


@app.patch("/api/orders/{order_id}", dependencies=[Depends(require_admin)])
def update_order_status(order_id: str, body: OrderStatus):
    update: Dict[str, Any] = {"status": body.status}
    if body.payment_status:
        update["payment_status"] = body.payment_status
    res = db["order"].update_one({"_id": ObjectId(order_id)}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"ok": True}


# ---------- Reviews (public read, admin seed) ----------
@app.get("/api/reviews")
def get_reviews():
    rows = db["review"].find({}).sort("created_at", -1).limit(20)
    return [serialize_doc(r) for r in rows]


@app.post("/api/reviews/seed", dependencies=[Depends(require_admin)])
def seed_reviews():
    if db["review"].count_documents({}) > 0:
        return {"message": "Reviews already exist"}
    sample = [
        {"name": "Aarav", "rating": 5, "comment": "Sensational kokum fish curry and the Sol Kadhi was a perfect finish.", "city": "Mumbai"},
        {"name": "Meera", "rating": 5, "comment": "Warm hospitality, refined flavours, and gorgeous interiors.", "city": "Pune"},
        {"name": "Zahir", "rating": 4, "comment": "Goan prawn croquettes are a must-try. Will be back!", "city": "Mumbai"},
    ]
    for r in sample:
        db["review"].insert_one({**r, "created_at": datetime.now(timezone.utc)})
    return {"inserted": len(sample)}


# ---------- Analytics (admin) ----------
@app.get("/api/analytics", dependencies=[Depends(require_admin)])
def analytics():
    # top items by quantity
    pipeline = [
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.name", "qty": {"$sum": "$items.qty"}}},
        {"$sort": {"qty": -1}},
        {"$limit": 5},
    ]
    top_items = list(db["order"].aggregate(pipeline))
    for t in top_items:
        t["name"] = t.pop("_id")
    # daily orders last 7 days
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)
    daily = list(db["order"].aggregate([
        {"$match": {"created_at": {"$gte": start}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]))
    return {"top_items": top_items, "daily_orders": daily}


# ---------- Utility ----------
@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
