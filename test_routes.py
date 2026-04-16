import httpx
import asyncio
import os

BASE_URL = "http://localhost:9009/api/v1"
SA_CREDS = {"email": "etogafranck449@gmail.com", "password": "Kafkatech"}
FR_CREDS = {"email": "test.fremium@kafkalearn.cm", "password": "Test1234!"}
REAL_PDF = "data/epreuves/Mathematiques/1902a056_Maths-3eme-Eval3.pdf"

async def login(email, password):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
        return resp.json()["access_token"] if resp.status_code == 200 else None

async def run_full_tests(token, user_type):
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        print(f"\n=== TESTS COMPLETS POUR {user_type} ===")
        
        # 1. Stats & List
        r = await client.get(f"{BASE_URL}/user-documents/stats")
        print(f"Stats: {r.status_code}")
        r = await client.get(f"{BASE_URL}/user-documents/")
        print(f"List: {r.status_code}")
        
        # 2. Upload un VRAI PDF
        print(f"Upload du fichier: {REAL_PDF}...")
        with open(REAL_PDF, "rb") as f:
            files = {"file": (os.path.basename(REAL_PDF), f, "application/pdf")}
            data = {"titre": f"Test Real {user_type}", "subject": "Mathématiques", "language": "fr"}
            r = await client.post(f"{BASE_URL}/user-documents/upload", files=files, data=data)
            
        if r.status_code != 201:
            print(f"[-] Échec upload: {r.status_code} - {r.text}")
            return
            
        doc_id = r.json().get("document_id")
        print(f"[+] Document uploadé avec succès ID: {doc_id}")
        
        # 3. Détail, Update, Download
        r = await client.get(f"{BASE_URL}/user-documents/{doc_id}")
        print(f"Detail: {r.status_code}")
        r = await client.patch(f"{BASE_URL}/user-documents/{doc_id}", json={"titre": f"Updated Title {user_type}"})
        print(f"Update: {r.status_code}")
        r = await client.get(f"{BASE_URL}/user-documents/{doc_id}/download")
        print(f"Download: {r.status_code}")
        
        # 4. Vectorize (Devrait être 403 pour Freemium, 202 ou 400 pour SuperAdmin si pas Premium)
        r = await client.post(f"{BASE_URL}/user-documents/{doc_id}/vectorize")
        print(f"Vectorize: {r.status_code}")
        
        # 5. Analysis (On attend un peu pour l'extraction)
        print("Attente de l'extraction (2s)...")
        await asyncio.sleep(2)
        r = await client.post(f"{BASE_URL}/documents/analyze", params={"document_id": doc_id})
        print(f"Analyze: {r.status_code}")
        
        if r.status_code == 200:
            print("[+] Analyse réussie !")
            r = await client.get(f"{BASE_URL}/documents/analyze/{doc_id}")
            print(f"Get Analysis Cache: {r.status_code}")
            r = await client.post(f"{BASE_URL}/documents/analyze/{doc_id}/refresh")
            print(f"Refresh Analysis: {r.status_code}")
            r = await client.post(f"{BASE_URL}/documents/analyze/{doc_id}/feedback", json={"est_utile": True})
            print(f"Feedback Analysis: {r.status_code}")
        else:
            print(f"[-] Échec Analyse: {r.text}")

        # 6. Admin Stats (Uniquement SuperAdmin)
        if user_type == "SuperAdmin":
            print("\n--- Tests Admin (SuperAdmin) ---")
            r = await client.get(f"{BASE_URL}/admin/user-documents/stats")
            print(f"Admin UserDoc Stats: {r.status_code}")
            r = await client.post(f"{BASE_URL}/admin/user-documents/retry-extractions")
            print(f"Admin Retry Extractions: {r.status_code}")
            r = await client.get(f"{BASE_URL}/admin/doc-analysis/stats")
            print(f"Admin DocAnalysis Stats: {r.status_code}")
            r = await client.get(f"{BASE_URL}/admin/doc-analysis/low-quality")
            print(f"Admin Low Quality: {r.status_code}")

async def main():
    sa_token = await login(SA_CREDS["email"], SA_CREDS["password"])
    fr_token = await login(FR_CREDS["email"], FR_CREDS["password"])
    
    if sa_token:
        await run_full_tests(sa_token, "SuperAdmin")
    if fr_token:
        await run_full_tests(fr_token, "Freemium")

if __name__ == "__main__":
    asyncio.run(main())
