import httpx
import asyncio

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_timetable_delete():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        print("\n=== TEST TIMETABLE DELETE ===")
        
        # 1. Create entry
        entry_data = {
            "subject": "Mathématiques",
            "day_of_week": 1,
            "start_time": "08:00",
            "end_time": "10:00"
        }
        r = await client.post(f"{BASE_URL}/timetable/", json=entry_data)
        print(f"Create Entry: {r.status_code}")
        
        if r.status_code == 201:
            entry_id = r.json()["entry"]["id"]
            print(f"[+] Entry created: {entry_id}")
            
            # 2. Delete entry
            r = await client.delete(f"{BASE_URL}/timetable/{entry_id}")
            print(f"Delete Entry: {r.status_code}")
            
            # 3. Check list
            r = await client.get(f"{BASE_URL}/timetable/")
            entries = r.json()["entries"]
            is_deleted = all(e["id"] != entry_id for e in entries)
            print(f"[+] Entry gone from list: {is_deleted}")
        else:
            print(f"[-] Create Entry failed: {r.text}")

if __name__ == "__main__":
    asyncio.run(test_timetable_delete())
