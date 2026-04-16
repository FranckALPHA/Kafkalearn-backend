import httpx
import asyncio
import json

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_skills():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        print("\n=== TESTS SKILLS ===")
        
        # 1. List Skills
        r = await client.get(f"{BASE_URL}/skills/liste")
        print(f"List Skills: {r.status_code}")
        if r.status_code == 200:
            print(f"Skills: {[s['type'] for s in r.json().get('skills', [])]}")
        
        # 2. Detect Intent
        r = await client.post(f"{BASE_URL}/skills/detecter", json={"texte": "quiz sur les dérivées"})
        print(f"Detect Intent: {r.status_code}")
        if r.status_code == 200:
            print(f"Detected: {r.json().get('skill_detecte')}")

        # 3. Run Skill (tuteur simple)
        payload = {
            "skill": "tuteur",
            "prompt": "Explique-moi la dérivée d'une fonction simple",
            "params": {"matiere": "Mathématiques"}
        }
        r = await client.post(f"{BASE_URL}/skills/run", json=payload)
        print(f"Run Skill (Tuteur): {r.status_code}")
        if r.status_code == 200:
             print(f"Result (first 100 chars): {r.json().get('content', '')[:100]}")

if __name__ == "__main__":
    asyncio.run(test_skills())
