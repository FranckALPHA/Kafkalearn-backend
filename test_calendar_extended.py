import httpx
import asyncio
from datetime import datetime

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_calendar_extended():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        print("\n=== TESTS CALENDAR EXTENDED ===")
        
        # 1. Timetable
        r = await client.get(f"{BASE_URL}/timetable/")
        print(f"List Timetable: {r.status_code}")
        
        # 2. Personal Plan
        r = await client.get(f"{BASE_URL}/personal-plan/")
        print(f"List Personal Plan: {r.status_code}")
        
        # 3. Reports
        r = await client.get(f"{BASE_URL}/reports/performance")
        print(f"Performance Report: {r.status_code}")
        
        r = await client.get(f"{BASE_URL}/reports/weekly-summary")
        print(f"Weekly Summary: {r.status_code}")
        
        # Test creation d'une entrée Timetable
        entry_data = {
            "jour_semaine": 1,
            "heure_debut": "08:00",
            "heure_fin": "10:00",
            "matiere": "Mathématiques"
        }
        r = await client.post(f"{BASE_URL}/timetable/", json=entry_data)
        print(f"Create Timetable Entry: {r.status_code}")
        if r.status_code == 201:
            entry_id = r.json()["id"]
            r = await client.delete(f"{BASE_URL}/timetable/{entry_id}")
            print(f"Delete Timetable Entry: {r.status_code}")

if __name__ == "__main__":
    asyncio.run(test_calendar_extended())
