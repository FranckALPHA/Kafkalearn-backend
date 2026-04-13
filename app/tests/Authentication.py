#POST /api/v1/auth/register Register

curl -X 'POST' \
  'http://127.0.0.1:9880/api/v1/auth/register' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "franckfranck449@gmail.com",
  "password": "franck123",
  "prenom": "franck",
  "langue": "fr",
  "referral_code": "REF-ABC123"
}'