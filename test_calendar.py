import httpx
import asyncio
from datetime import datetime, timedelta

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_calendar():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        print("\n=== TESTS CALENDAR SESSIONS ===")
        
        # 1. Create Session
        now = datetime.now().isoformat()
        session_data = {
            "subject": "Mathématiques",
            "titre": "Session de test",
            "planned_start": now,
            "planned_duration_minutes": 30,
            "is_ai_generated": False,
            "humeur_debut": "neutre"
        }
        r = await client.post(f"{BASE_URL}/sessions", json=session_data)
        print(f"Create Session: {r.status_code}")
        if r.status_code != 201:
            print(f"[-] Erreur creation: {r.text}")
            return
        
        session_id = r.json()["id"]
        print(f"[+] Session ID: {session_id}")

        # 2. List Sessions
        r = await client.get(f"{BASE_URL}/sessions")
        print(f"List Sessions: {r.status_code}")
        
        # 3. Ping
        r = await client.post(f"{BASE_URL}/sessions/{session_id}/ping", json={"elapsed_client": 60})
        print(f"Ping Session: {r.status_code}")
        
        # 4. Update Status (Complete)
        r = await client.patch(f"{BASE_URL}/sessions/{session_id}/status", json={"status": "completed", "note_session": 5})
        print(f"Update Status (completed): {r.status_code}")
        
        # 5. Get Suggestions
        r = await client.get(f"{BASE_URL}/suggestions")
        print(f"Suggestions: {r.status_code}")
        
        # 6. Coach Insights
        r = await client.get(f"{BASE_URL}/coach-insights")
        print(f"Coach Insights: {r.status_code}")
        
        # 7. Heatmap
        r = await client.get(f"{BASE_URL}/heatmap")
        print(f"Heatmap: {r.status_code}")
        print(f"Result: {r.json().get('total')} sessions total.")

if __name__ == "__main__":
    asyncio.run(test_calendar())
