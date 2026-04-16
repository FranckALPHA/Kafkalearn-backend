import httpx
import asyncio
import json

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}
BATCH_DIR = "data/batch_test"

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_batch_ingest():
    token = await login()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=300.0) as client:
        print(f"\n=== TEST INGESTION BATCH : {BATCH_DIR} ===")
        
        # Lancer l'ingestion du dossier
        r = await client.post(f"{BASE_URL}/ingest/scan-folder", json={"chemin_dossier": BATCH_DIR})
        print(f"Scan Folder Triggered: {r.status_code}")
        
        if r.status_code != 200:
            print(f"[-] Scan folder failed: {r.text}")
            return

        print("[*] Attente de la fin du traitement (60s)...")
        # On attend que l'ingestion traite les 10 fichiers
        await asyncio.sleep(60)

        # Vérifier si les documents sont créés (devraient avoir 10 nouveaux docs)
        r = await client.get(f"{BASE_URL}/user-documents/")
        docs = r.json().get("documents", [])
        print(f"[+] Nombre total de documents après scan: {len(docs)}")
        
        # Vérifier si la mémoire est générée pour au moins un des fichiers
        # On cherche un doc qui a des sections
        for doc in docs[:10]: # Vérifions les 10 plus récents
            r = await client.get(f"{BASE_URL}/memory/sections", params={"document_id": doc["id"]})
            if r.status_code == 200 and r.json().get("sections"):
                print(f"[+] Mémoire générée pour doc {doc['id']}: {len(r.json()['sections'])} sections.")
                return

        print("[-] Aucune section mémoire générée après scan.")

if __name__ == "__main__":
    asyncio.run(test_batch_ingest())
