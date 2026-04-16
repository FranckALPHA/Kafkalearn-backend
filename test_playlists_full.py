import httpx
import asyncio

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_playlists_full():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        print("\n=== TESTS COMPLETS PLAYLISTS ===")
        
        # 1. Create
        r = await client.post(f"{BASE_URL}/epreuves/playlists/", json={"nom": "Playlist Test"})
        print(f"Create status: {r.status_code}, Response: {r.json()}")
        playlist_id = r.json().get("id")
        if not playlist_id:
            print("[-] Create failed to return ID")
            return
        print(f"[+] Created: {playlist_id}")

        # 2. Add Document (Document ID 135)
        r = await client.post(f"{BASE_URL}/epreuves/playlists/{playlist_id}/documents", json={"document_id": 135})
        print(f"Add Doc: {r.status_code}")

        # 3. Share
        r = await client.post(f"{BASE_URL}/epreuves/playlists/{playlist_id}/share")
        print(f"Share: {r.status_code}")

        # 4. Copy (Public Playlist)
        # On utilise le même ID pour tester la copie
        r = await client.post(f"{BASE_URL}/epreuves/playlists/copy/{playlist_id}")
        print(f"Copy: {r.status_code}")

        # 5. Remove Doc
        r = await client.delete(f"{BASE_URL}/epreuves/playlists/{playlist_id}/documents/135")
        print(f"Remove Doc: {r.status_code}")

        # 6. Delete Playlist
        r = await client.delete(f"{BASE_URL}/epreuves/playlists/{playlist_id}")
        print(f"Delete Playlist: {r.status_code}")

if __name__ == "__main__":
    asyncio.run(test_playlists_full())
