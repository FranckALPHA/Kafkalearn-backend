import httpx
import asyncio

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_admin_epreuves():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        print("\n=== TESTS ADMIN EPREUVES ===")
        
        # 1. Stats
        r = await client.get(f"{BASE_URL}/admin/epreuves/stats")
        print(f"Stats: {r.status_code}")
        
        # 2. Pending Ingestion
        r = await client.get(f"{BASE_URL}/admin/epreuves/pending-ingestion")
        print(f"Pending: {r.status_code}")
        
        # 3. Invalidate Cache
        r = await client.post(f"{BASE_URL}/admin/epreuves/invalidate-cache")
        print(f"Invalidate Cache: {r.status_code}")
        
        # 4. Trigger Ingestion (ID 135)
        r = await client.post(f"{BASE_URL}/admin/epreuves/ingest/135")
        print(f"Trigger Ingest (135): {r.status_code}")
        print(f"Detail: {r.text}")

if __name__ == "__main__":
    asyncio.run(test_admin_epreuves())
