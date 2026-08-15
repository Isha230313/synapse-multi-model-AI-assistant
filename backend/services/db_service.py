"""
Database Service - MongoDB (history) + Redis (person profile cache)
"""
import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# MongoDB
# ─────────────────────────────────────────────
_mongo_client = None
_mongo_db = None

async def connect_mongo():
    global _mongo_client, _mongo_db
    url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB", "synapse")
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        _mongo_client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=3000)
        await _mongo_client.server_info()
        _mongo_db = _mongo_client[db_name]
        logger.info(f"✅ MongoDB connected: {url} / {db_name}")
    except Exception as e:
        logger.warning(f"⚠️  MongoDB unavailable: {e}. History will use local file fallback.")
        _mongo_client = None
        _mongo_db = None

async def disconnect_mongo():
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        logger.info("MongoDB disconnected.")

def is_mongo_available() -> bool:
    return _mongo_db is not None


# ─────────────────────────────────────────────
# MongoDB — Search History
# ─────────────────────────────────────────────
async def mongo_save_entry(message: str, response_type: str):
    if not is_mongo_available():
        return
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    entry = {
        'message': message,
        'type': response_type,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    await _mongo_db.history.update_one(
        {'date': today},
        {'$push': {'entries': entry}, '$setOnInsert': {'date': today}},
        upsert=True
    )

async def mongo_get_history() -> list:
    if not is_mongo_available():
        return []
    cursor = _mongo_db.history.find({}, {'_id': 0}).sort('date', -1)
    return await cursor.to_list(length=None)

async def mongo_clear_history():
    if not is_mongo_available():
        return
    await _mongo_db.history.delete_many({})


# ─────────────────────────────────────────────
# MongoDB — Person Profiles
# ─────────────────────────────────────────────
async def mongo_save_profile(name: str, profile: dict):
    if not is_mongo_available():
        return
    await _mongo_db.profiles.update_one(
        {'_name': name.lower()},
        {'$set': {**profile, '_name': name.lower(), '_saved_at': datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )

async def mongo_get_profile(name: str) -> dict | None:
    if not is_mongo_available():
        return None
    doc = await _mongo_db.profiles.find_one({'_name': name.lower()}, {'_id': 0, '_name': 0, '_saved_at': 0})
    return doc or None


# ─────────────────────────────────────────────
# Redis
# ─────────────────────────────────────────────
_redis = None
CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", "86400"))  # 24 hours default

async def connect_redis():
    global _redis
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.Redis(host=host, port=port, decode_responses=True)
        await _redis.ping()
        logger.info(f"✅ Redis connected: {host}:{port}")
    except Exception as e:
        logger.warning(f"⚠️  Redis unavailable: {e}. Caching disabled.")
        _redis = None

async def disconnect_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        logger.info("Redis disconnected.")

def is_redis_available() -> bool:
    return _redis is not None


# ─────────────────────────────────────────────
# Redis — Person Profile Cache
# ─────────────────────────────────────────────
async def cache_get_profile(name: str) -> dict | None:
    if not is_redis_available():
        return None
    try:
        raw = await _redis.get(f"person:{name.lower()}")
        if raw:
            logger.info(f"✅ Redis cache hit: {name}")
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"Redis get error: {e}")
    return None

async def cache_set_profile(name: str, profile: dict):
    if not is_redis_available():
        return
    try:
        await _redis.setex(f"person:{name.lower()}", CACHE_TTL, json.dumps(profile))
        logger.info(f"✅ Redis cached: {name} (TTL {CACHE_TTL}s)")
    except Exception as e:
        logger.warning(f"Redis set error: {e}")
