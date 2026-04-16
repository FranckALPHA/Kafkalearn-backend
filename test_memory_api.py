import httpx
import asyncio
import json

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}
DOC_ID = 135

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_memory_routes():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        print(f"\n=== TESTS MEMORY (DOC ID: {DOC_ID}) ===")
        
        # 1. List Sections
        r = await client.get(f"{BASE_URL}/memory/sections", params={"document_id": DOC_ID})
        print(f"List Sections: {r.status_code}")
        sections = r.json().get("sections", [])
        if not sections:
            print("[-] No sections found")
            return
        
        section_id = sections[0]["id"]
        print(f"[+] Section found: {sections[0]['section_title']} (ID: {section_id})")

        # 2. Get Items
        r = await client.get(f"{BASE_URL}/memory/sections/{section_id}/items")
        print(f"Get Items: {r.status_code}")
        items = r.json().get("items", [])
        if not items:
            print("[-] No items found")
            return
        
        item_id = items[0]["id"]
        print(f"[+] Item found: {items[0]['recto']} (ID: {item_id})")

        # 3. Get Verso
        r = await client.get(f"{BASE_URL}/memory/sections/{section_id}/items/{item_id}/verso")
        print(f"Get Verso: {r.status_code}")
        print(f"    Verso: {r.json().get('verso') or r.json().get('bonne_reponse')}")

        # 4. Submit Answer
        ans = {"reponse": "Yaoundé", "qualite": 5, "duree_secondes": 10}
        r = await client.post(f"{BASE_URL}/memory/sections/{section_id}/items/{item_id}/repondre", json=ans)
        print(f"Submit Answer: {r.status_code}")
        print(f"    Result: {r.json()}")

        # 5. Complete Section
        r = await client.post(f"{BASE_URL}/memory/sections/{section_id}/complete", json={})
        print(f"Complete Section: {r.status_code}")
        print(f"    Result: {r.json()}")

        # 6. Today Reviews
        r = await client.get(f"{BASE_URL}/memory/today")
        print(f"Today Reviews: {r.status_code}")

        # 7. Stats
        r = await client.get(f"{BASE_URL}/memory/stats")
        print(f"Memory Stats: {r.status_code}")
        print(f"    Stats: {json.dumps(r.json(), indent=2)}")

if __name__ == "__main__":
    asyncio.run(test_memory_routes())
