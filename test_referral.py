import httpx
import asyncio

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_referral():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        print("\n=== TESTS REFERRAL ===")
        
        # 1. My Stats
        r = await client.get(f"{BASE_URL}/referral/me")
        print(f"Referral Stats: {r.status_code}")
        if r.status_code == 200:
            print(f"Stats: {r.json()}")
        
        # 2. Rewards
        r = await client.get(f"{BASE_URL}/referral/rewards")
        print(f"Rewards: {r.status_code}")
        
        # 3. Check Code (Invalid code)
        r = await client.get(f"{BASE_URL}/referral/check/FAKECODE123")
        print(f"Check Invalid Code: {r.status_code}")
        
        # 4. QR Code
        r = await client.get(f"{BASE_URL}/referral/me/qr-code")
        print(f"QR Code: {r.status_code}")
        if r.status_code == 200:
            print(f"[+] QR Code generated ({len(r.content)} bytes)")
        else:
            print(f"[-] QR Code generation: {r.text}")

if __name__ == "__main__":
    asyncio.run(test_referral())
