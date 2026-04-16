import httpx
import asyncio
import json

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_performance_report():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        print("\n=== TEST PERFORMANCE REPORT ===")
        r = await client.get(f"{BASE_URL}/reports/performance")
        print(f"Performance Report Status: {r.status_code}")
        
        if r.status_code == 200:
            print("Response content:")
            print(json.dumps(r.json(), indent=2))
        else:
            print(f"[-] Erreur: {r.text}")

if __name__ == "__main__":
    asyncio.run(test_performance_report())
