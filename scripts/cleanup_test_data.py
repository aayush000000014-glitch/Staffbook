import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    bids = [b["id"] for b in await db.businesses.find({"name": {"$regex": "^TEST_"}}, {"id": 1}).to_list(None)]
    uids = [u["id"] for u in await db.users.find({"business_id": {"$in": bids}}, {"id": 1}).to_list(None)]
    for c in ["staff", "attendance", "obligations", "transactions", "advances", "advance_recoveries", "fines",
              "audit_logs", "notifications", "memberships"]:
        await db[c].delete_many({"business_id": {"$in": bids}})
    await db.sessions.delete_many({"user_id": {"$in": uids}})
    await db.users.delete_many({"id": {"$in": uids}})
    await db.businesses.delete_many({"id": {"$in": bids}})
    print("cleaned businesses:", len(bids))


asyncio.run(main())
