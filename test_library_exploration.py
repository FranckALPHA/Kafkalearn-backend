import httpx
import asyncio

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_library():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        print("\n=== TESTS LIBRARY EXPLORATION ===")
        
        # 1. List
        r = await client.get(f"{BASE_URL}/library/")
        print(f"List: {r.status_code}")
        print(f"Content: {r.text[:500]}") # Affichage partiel
        
        # 2. Public
        r = await client.get(f"{BASE_URL}/library/public/")
        print(f"Public Library: {r.status_code}")
        
        # 3. Stats (Admin)
        r = await client.get(f"{BASE_URL}/admin/library/stats")
        print(f"Admin Stats: {r.status_code}")
        print(f"Result: {r.json()}")

if __name__ == "__main__":
    asyncio.run(test_library())
