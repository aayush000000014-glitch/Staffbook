# StaffBook — PRD

## Original problem statement
BUILD STAFFBOOK — COMPLETE STAFF MANAGEMENT SAAS. A complete, functional, mobile-first, multi-tenant SaaS web application for Indian small businesses (shops, restaurants, medical stores). Real DB, auth, authorization, business logic. Palette #171717 / #F7F5F0 / #8B1E2D / #C6A15B. Phone (+91) auth, onboarding wizard, 3 roles (Super Admin, Owner, Staff), tenant isolation, live dashboard, staff management (100 active limit, Mark as Left), exception-based attendance, salary engine (Fixed 30 / Calendar days), 3 payment schedules (fixed date / 30-day / 40-day), payments (partial, cash/UPI/bank, renewal option, audit), advances & recoveries, manual & late fines, paid-leave quota (≤5, monthly/yearly), final settlement, payment calendar, 8 reports with CSV/PDF, Super Admin panel, in-app notifications only, settings. (Full text in first user message of the job.)

## User choices
- Mobile (+91) + password, JWT sessions · MongoDB with server-side tenant isolation · Security-question password recovery · Images as base64 (<1MB) in DB · Super admin from env (8950771876).

## Architecture
- Stack: React 19 (CRA + Tailwind + shadcn) · FastAPI · MongoDB (Motor). Auth: custom JWT (PyJWT, bcrypt), Bearer token in localStorage, 7-day expiry.
- Backend modules: core.py (db, auth deps, owner_ctx/member_ctx/admin_user, audit), engine.py (pure salary/schedule math), services.py (Ledger, obligation sync, staff creation with atomic 100-limit counter), routes_auth/business/staff/pay/reports/admin.py.
- Collections: users, businesses (settings embedded, active_staff_count), memberships, staff, attendance (unique staff_id+date), obligations (unique staff_id+period_start; snapshot salary/method), transactions (unique client_ref; valid/reversed), advances, advance_recoveries (unique obligation_id), fines, audit_logs, notifications (unique key), login_attempts.
- Tenant isolation: every owner query filtered by business_id from server-side membership; deactivated businesses blocked in dependency.
- Financial integrity: transactions never overwritten (reversal only), optimistic version lock on obligations, edits to fully-paid periods blocked.
- Env vars (backend): MONGO_URL, DB_NAME, CORS_ORIGINS, JWT_SECRET, SUPER_ADMIN_PHONE, SUPER_ADMIN_PASSWORD, SUPER_ADMIN_EMAIL. Frontend: REACT_APP_BACKEND_URL.

## Personas
Business owner (daily use on phone), Staff (read-only own salary), Super Admin (platform).

## Implemented (2026-10-14)
- All milestones 1–5 + responsive UI; 8 engine unit tests + 23 API tests (backend/tests) passing; testing agent iteration_1: 100% backend, UI smoke pass.
- PDF = browser print / Save as PDF of report page (no server PDF).
- Known limitations: MongoDB standalone (no multi-doc transactions; integrity via unique indexes + atomic updates + version lock); no OTP (by design); staff password reset is done by owner; recovery/question endpoint reveals whether a number is registered.

## Backlog
- P1: Server-generated PDF files; rehire former staff; bulk attendance for all staff on a date.
- P2: Pagination for large histories; rate limit on signup/recovery-question; GitHub/Vercel deployment (frontend only — backend needs a Python host).

## Deployment
Use Emergent Deploy (handles FastAPI + MongoDB + env). For Vercel, only the React frontend can be hosted; backend needs a Python host + MongoDB Atlas and the env vars above.
