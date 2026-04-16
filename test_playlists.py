import httpx
import asyncio

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_playlists():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        print("\n=== TESTS PLAYLISTS ===")
        
        # 1. List
        r = await client.get(f"{BASE_URL}/epreuves/playlists/")
        print(f"List: {r.status_code}")
        
        # 2. Create
        data = {"nom": "Test Playlist", "description": "Ma playlist de test"}
        r = await client.post(f"{BASE_URL}/epreuves/playlists/", json=data)
        print(f"Create: {r.status_code}")
        if r.status_code != 201: return
        playlist_id = r.json()["id"]
        
        # 3. Add Doc (ID 135)
        r = await client.post(f"{BASE_URL}/epreuves/playlists/{playlist_id}/documents", json={"document_id": 135})
        print(f"Add Doc: {r.status_code}")
        
        # 4. Get Detail
        r = await client.get(f"{BASE_URL}/epreuves/playlists/{playlist_id}")
        print(f"Detail: {r.status_code}")
        
        # 5. Share
        r = await client.post(f"{BASE_URL}/epreuves/playlists/{playlist_id}/share")
        print(f"Share: {r.status_code}")
        
        # 6. Copy
        r = await client.post(f"{BASE_URL}/epreuves/playlists/copy/{playlist_id}")
        print(f"Copy: {r.status_code}")
        
        # 7. Remove Doc
        r = await client.delete(f"{BASE_URL}/epreuves/playlists/{playlist_id}/documents/135")
        print(f"Remove Doc: {r.status_code}")
        
        # 8. Delete Playlist
        r = await client.delete(f"{BASE_URL}/epreuves/playlists/{playlist_id}")
        print(f"Delete Playlist: {r.status_code}")

if __name__ == "__main__":
    asyncio.run(test_playlists())
