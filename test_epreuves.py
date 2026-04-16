import httpx
import asyncio

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_epreuves():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        print("\n=== TESTS EPREUVES ===")
        
        # 1. List
        r = await client.get(f"{BASE_URL}/epreuves/")
        print(f"List Documents: {r.status_code}")
        
        # 2. Filters
        r = await client.get(f"{BASE_URL}/epreuves/filtres")
        print(f"Filters: {r.status_code}")
        if r.status_code == 422: print(f"    Detail: {r.text}")
        
        # 3. Trending
        r = await client.get(f"{BASE_URL}/epreuves/trending")
        print(f"Trending: {r.status_code}")
        if r.status_code == 422: print(f"    Detail: {r.text}")
        
        # 4. Upload (Test avec fichier existant)
        print("[*] Uploading test file...")
        pdf_path = "data/epreuves/Mathematiques/1902a056_Maths-3eme-Eval3.pdf"
        with open(pdf_path, "rb") as f:
            files = {"file": ("test_upload.pdf", f, "application/pdf")}
            data = {"nom_affiche": "Test Doc Epreuve", "matiere": "Mathématiques"}
            r = await client.post(f"{BASE_URL}/epreuves/upload", files=files, data=data)
        print(f"Upload: {r.status_code}")
        
        if r.status_code == 201:
            doc_id = r.json()["id"]
            
            # 5. Detail
            r = await client.get(f"{BASE_URL}/epreuves/{doc_id}")
            print(f"Detail: {r.status_code}")
            
            # 6. Stats
            r = await client.get(f"{BASE_URL}/epreuves/{doc_id}/stats")
            print(f"Stats: {r.status_code}")
            
            # 7. Download
            r = await client.get(f"{BASE_URL}/epreuves/{doc_id}/download")
            print(f"Download: {r.status_code}")

if __name__ == "__main__":
    asyncio.run(test_epreuves())
