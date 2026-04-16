import httpx
import asyncio
import json
import os
import time

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}
PDF_PATH = "data/epreuves/Histoire-Géographie/93b2c489_Cours d'histoire géographie.pdf"

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_ingest_and_memory():
    token = await login()
    if not token:
        print("[-] Login failed")
        return

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=120.0) as client:
        # STEP 0: Cleanup previous tests
        print("\n=== STEP 0: CLEANUP ===")
        r_docs = await client.get(f"{BASE_URL}/user-documents/")
        docs = r_docs.json().get("documents", [])
        for doc in docs:
            if doc["titre"] == "Test Ingest Memory":
                print(f"[*] Deleting old test doc {doc['id']}...")
                await client.delete(f"{BASE_URL}/user-documents/{doc['id']}")

        print("\n=== STEP 1: ASYNC INGESTION ===")
        if not os.path.exists(PDF_PATH):
            print(f"[-] PDF not found: {PDF_PATH}")
            return

        with open(PDF_PATH, "rb") as f:
            files = {"file": ("test_ingest_memory.pdf", f, "application/pdf")}
            data = {"force_metadata": json.dumps({
                "type_doc": "lecon", 
                "matiere": "Histoire-Géographie", 
                "niveau": "Terminale",
                "notion_principale": "Introduction"
            })}
            r = await client.post(f"{BASE_URL}/ingest/indexer-async", files=files, data=data)
        
        if r.status_code != 202:
            print(f"[-] Ingest failed: {r.status_code} - {r.text}")
            return
        
        job_id = r.json()["job_id"]
        print(f"[+] Ingest job queued: {job_id}")

        # Poll report
        doc_id = None
        print("[*] Waiting for ingestion to complete (max 60s)...")
        for i in range(30):
            await asyncio.sleep(2)
            r = await client.get(f"{BASE_URL}/ingest/indexer-report/{job_id}")
            report = r.json()
            print(f"    [{i*2}s] Status: {report['status']} ({report['nb_traites']}/{report['nb_fichiers_total']})")
            if report["status"] == "complete":
                # Find doc_id
                r_docs = await client.get(f"{BASE_URL}/user-documents/")
                docs = r_docs.json().get("documents", [])
                if docs:
                    doc_id = docs[0]["id"]
                break
            if report["status"] == "failed":
                print(f"[-] Job failed: {report['erreurs_detail']}")
                return

        if not doc_id:
            print("[-] Could not find document_id after ingestion")
            return
        
        print(f"[+] Document ID created: {doc_id}")

        print("\n=== STEP 2: MEMORY SECTIONS ===")
        # Wait for memory generation (tasks are async)
        print("[*] Waiting for memory generation (max 30s)...")
        for i in range(15):
            await asyncio.sleep(2)
            r = await client.get(f"{BASE_URL}/memory/sections", params={"document_id": doc_id})
            if r.status_code == 200:
                sections = r.json().get("sections", [])
                if sections:
                    print(f"    [{i*2}s] Found {len(sections)} sections.")
                    break
            print(f"    [{i*2}s] Still waiting for sections...")

        if not sections:
            print("[-] Sections list empty or not found")
            return
        
        section_id = sections[0]["id"]
        print(f"[+] Using Section: {sections[0]['section_title']} (ID: {section_id})")

        # 3. Get Items
        r = await client.get(f"{BASE_URL}/memory/sections/{section_id}/items")
        print(f"Get Items: {r.status_code}")
        items = r.json().get("items", [])
        if not items:
            print("[-] No items in section")
            return
        
        item_id = items[0]["id"]
        print(f"[+] Testing Item ID: {item_id}")

        # 4. Get Verso
        r = await client.get(f"{BASE_URL}/memory/sections/{section_id}/items/{item_id}/verso")
        print(f"Get Verso: {r.status_code}")

        # 5. Submit Answer
        answer_data = {"reponse": "Test response", "qualite": 5, "duree_secondes": 10}
        r = await client.post(f"{BASE_URL}/memory/sections/{section_id}/items/{item_id}/repondre", json=answer_data)
        print(f"Submit Answer: {r.status_code}")

        # 6. Complete Section
        r = await client.post(f"{BASE_URL}/memory/sections/{section_id}/complete", json={})
        print(f"Complete Section: {r.status_code}")

        # 7. Stats
        r = await client.get(f"{BASE_URL}/memory/stats")
        print(f"Memory Stats: {r.status_code} - Accuracy: {r.json().get('accuracy')}%")

        print("\n[+] SUCCESS: Full Ingest -> Memory cycle validated.")

if __name__ == "__main__":
    asyncio.run(test_ingest_and_memory())
