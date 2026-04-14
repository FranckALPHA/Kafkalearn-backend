curl -X POST "http://127.0.0.1:9880/api/v1/auth/register" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "franckfranck449@gmail.com",
    "password": "Franck123",
    "prenom": "Franck",
    "langue": "fr",
    "referral_code": "REF-ABC123"
  }'