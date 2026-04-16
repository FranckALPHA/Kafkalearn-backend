import os
import shutil
import logging
from app.core.database import SessionLocal, Base, engine
from app.core.config import REDIS_URL
from redis import Redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reset_script")

def reset_database():
    logger.info("Dropping and recreating database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables reset successfully.")

def reset_storage():
    storage_dirs = [
        "data/epreuves",
        "data/user_docs",
        "data/sandbox",
        "data/skills",
        "data/profiles",
        "data/assets"
    ]
    for directory in storage_dirs:
        if os.path.exists(directory):
            logger.info(f"Removing directory: {directory}")
            shutil.rmtree(directory)
            os.makedirs(directory)
    logger.info("Storage directories cleared.")

def reset_redis():
    logger.info("Clearing Redis cache...")
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    redis.flushall()
    logger.info("Redis cleared.")

def run_reset():
    try:
        reset_database()
        reset_storage()
        reset_redis()
        # Note: Search engines (Vespa/MeiliSearch) would require additional API calls
        logger.info("Full reset complete. System is back to base state.")
    except Exception as e:
        logger.error(f"Reset failed: {e}")

if __name__ == "__main__":
    run_reset()
