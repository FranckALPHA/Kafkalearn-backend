import httpx
import asyncio

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}
DOC_ID = 135

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_memory_admin():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        print("\n=== TESTS MEMORY ADMIN & COGNITIVE ===")
        
        # 1. Admin Graph
        r = await client.get(f"{BASE_URL}/memory/admin/graph/global")
        print(f"Global Graph: {r.status_code}")
        r = await client.get(f"{BASE_URL}/memory/admin/graph/global/stats")
        print(f"Global Stats: {r.status_code}")
        r = await client.get(f"{BASE_URL}/memory/admin/graph/ambiguous")
        print(f"Ambiguous Notions: {r.status_code}")

        # 2. Cognitive Report
        r = await client.get(f"{BASE_URL}/memory/cognitive-report")
        print(f"Cognitive Report: {r.status_code}")
        
        # Deblocables
        r = await client.get(f"{BASE_URL}/memory/cognitive-report/deblocables")
        print(f"Deblocables: {r.status_code}")

        # 3. Graph Extraction (Test sur le doc 135)
        print(f"\n[*] Testing Extraction for Doc ID: {DOC_ID}")
        r = await client.post(f"{BASE_URL}/memory/admin/graph/extract-document", params={"document_id": DOC_ID})
        print(f"Extract Document: {r.status_code}")
        print(f"    Result: {r.text}")

if __name__ == "__main__":
    asyncio.run(test_memory_admin())
