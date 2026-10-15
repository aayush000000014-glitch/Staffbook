# Auth testing (StaffBook)
- Auth = phone (+91) + password, bcrypt hashes ($2b$).
- Sessions: opaque random token in HttpOnly + Secure + SameSite=Lax cookie `sb_session` (30 days, sliding renewal on /api/auth/me). Only SHA-256 hash stored in `sessions` collection (TTL index on expires_at_dt). Login/signup responses return only {user} (no token in body).
- For API tests use a cookie jar against the external https URL (cookie is Secure): `curl -c cj -b cj ...` or requests.Session(). A `Authorization: Bearer <cookie value>` header is also accepted.
- Logout (POST /api/auth/logout) deletes the server session + clears cookie; afterwards /api/auth/me = 401.
- Password change revokes other sessions; recovery reset revokes all sessions; staff marked as left -> disabled -> 401.
- Brute force: 5 failed logins per ip:phone -> 15 min lock (HTTP 429 from 6th attempt).
- Super admin seeded on startup; public signup always creates role=owner.
- Cleanup: python /app/scripts/cleanup_test_data.py (deletes all TEST_* businesses and their data/users/sessions).
