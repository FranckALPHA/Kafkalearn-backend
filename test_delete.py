import httpx
import asyncio

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}

async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json=SA_CREDS)
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def test_delete():
    token = await login()
    if not token:
        print("[-] Erreur Login")
        return

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers) as client:
        # On cherche d'abord le document que j'ai créé (probablement ID 1)
        r = await client.get(f"{BASE_URL}/user-documents/")
        docs = r.json().get("documents", [])
        
        if not docs:
            print("[-] Aucun document à supprimer pour le test.")
            return
        
        doc_id = docs[0]["id"]
        print(f"[*] Tentative de suppression du document ID: {doc_id} ({docs[0]['titre']})")
        
        # 1. Suppression
        r = await client.delete(f"{BASE_URL}/user-documents/{doc_id}")
        print(f"[DELETE /user-documents/{doc_id}] Status: {r.status_code}")
        
        if r.status_code == 204:
            print("[+] Suppression réussie (204 No Content)")
            
            # 2. Vérification (doit être 404)
            r = await client.get(f"{BASE_URL}/user-documents/{doc_id}")
            print(f"[GET /user-documents/{doc_id}] Post-suppression: {r.status_code} (Attendu: 404)")
            if r.status_code == 404:
                print("[+] Confirmation : Le document n'existe plus.")
        else:
            print(f"[-] Erreur lors de la suppression: {r.text}")

if __name__ == "__main__":
    asyncio.run(test_delete())
