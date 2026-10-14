# Auth testing (StaffBook)
- Auth = phone (+91) + password, bcrypt hashes ($2b$), JWT Bearer token (7 days) stored in localStorage key sb_token.
- Brute force: 5 failed logins per ip:phone -> 15 min lock (HTTP 429).
- Super admin seeded on startup; public signup always creates role=owner.
- Check: mongosh test_database --eval 'db.users.find({role:"super_admin"},{phone:1,role:1})'
- curl -X POST $URL/api/auth/login -H 'Content-Type: application/json' -d '{"phone":"8950771876","password":"@Aayush_0512"}'
