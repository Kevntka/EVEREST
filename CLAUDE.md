# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

EVEREST is an event registration system: an Angular 21 frontend plus a FastAPI + PostgreSQL backend.

## Repository layout gotchas

- **The real frontend is `frontend/event-registration/`.** It is a nested git repo (a gitlink in the outer repo, same GitHub remote), so commit changes to it from inside that directory. The root-level `src/`, `angular.json`, and `package.json` are an older copy that only has login and registration pages. Don't edit them unless asked.
- **The backend is `backend/`.** The active router is `backend/api/routes_db.py`. `backend/api/routes.py` is a legacy in-memory version that isn't mounted in `main.py`.
- Many one-off scripts in `backend/` (`setup_*.py`, `create_admin.py`, `check_*.py`, `test_smtp*.py`, and others) are manual utilities, not tests. Some are stale: `create_admin.py` imports a `Role` model that no longer exists.

## Commands

Frontend (run from `frontend/event-registration/`):

```bash
npm start                                  # ng serve on http://localhost:4200
npx ng build --configuration development   # quick compile check
npm test                                   # Vitest via ng test
npx ng test --include src/app/app.spec.ts  # single spec file
```

Backend (run from `backend/`. Imports and the `uploads/` path are relative to it):

```bash
venv\Scripts\activate                      # or: source venv/Scripts/activate (Git Bash)
python -m uvicorn main:app --reload        # http://localhost:8000; start_server.bat does this
```

There are no backend tests. Configuration comes from `backend/.env` (loaded with python-dotenv): `DATABASE_URL`, `JWT_SECRET_KEY`, `SMTP_*`, `EMAIL_ENABLED`, and `RECAPTCHA_SECRET_KEY`. The schema is in `backend/database/schema.sql`.

## Architecture

**Roles and pages.** There are four roles: `admin`, `organizer`, `student`, and `participant`. Each role has its own set of standalone page components under `src/app/components/`:
- Admin: `dashboard`, `organizer`, `students`, `participants`
- Organizer: `organizer-dashboard`, `organizer-events`, `organizer-attendance`
- Student: `student-dashboard`, `student-profile`, `event-details`

Each page component contains its own sidebar, top bar, and modals. There is no shared layout component, so a UI change to one page usually has to be repeated on its sibling pages.

**Change detection.** The app is zoneless: there's no zone.js, so views don't update on their own after async work. For HTTP responses, `interceptors/change-detection.interceptor.ts` (registered in `app.config.ts`) calls `markForCheck()` on the root components after each request's subscribe callbacks. Don't switch this to `ApplicationRef.tick()`: in zoneless mode, `tick()` skips views that aren't marked dirty. Its spec is the regression test. Other async sources, such as `setTimeout` or third-party callbacks, still need `ChangeDetectorRef.detectChanges()` or signals. Some components also call `cdr.detectChanges()` after HTTP responses. That code predates the interceptor and is now redundant, but it does no harm.

**API calls.** Components call `HttpClient` directly with hardcoded `http://localhost:8000/api/...` URLs. There is no API service layer. The backend's CORS setting only allows `localhost:4200`. Most endpoints take `multipart/form-data` (FastAPI `Form(...)`), so the frontend sends `FormData`.

**Authentication**
- `POST /api/login` verifies the reCAPTCHA token and sets an HTTP-only `access_token` JWT cookie.
- The frontend separately stores `userRole`, `userName`, `userId`, and, for organizers, `organizerId`/`organizerName` in `localStorage`.
- The route guards in `guards/auth.guard.ts` read only `localStorage`.
- Almost no backend endpoints check authentication. For example, `POST /api/events` trusts the `organizer_id` form field sent by the frontend.
- `interceptors/csrf.interceptor.ts` and `backend/auth/csrf_protection.py` exist, but the interceptor is commented out in `app.config.ts`.
- The reCAPTCHA site key is Google's test key.

**Data model** (`backend/models/user.py`, mirroring `schema.sql`)
- `users` holds identity, including the `role` string. `user_roles` holds per-role details: department, employment ID, and contact number.
- `events.user_role_id` references `user_roles.id`, not `users.id`. To link an event to an organizer, look up the organizer's `user_roles` row.
- `registrations.user_id` has **no** `ON DELETE CASCADE`. Delete a user's registrations before deleting the user. `attendees` cascade from `registrations`.
- Some endpoints use ORM models; others (events) use raw `text()` SQL.
- Event dates are serialized as `YYYY-MM-DD` strings, and the frontend compares them as strings.
- Event cover photos are stored in the database: the bytes go in `events.cover_photo_data` (BYTEA) and the MIME type in `cover_photo_type`, with a 5 MB limit. They're served by `GET /api/events/{id}/cover`. `events.cover_photo` holds that URL path, and the frontend prefixes it with `http://localhost:8000`. `backend/uploads/` and the `/uploads` static mount are leftovers from the old file-based storage.

## Styling conventions

- **Dark mode.** `ThemeService` toggles `body.dark-mode` and saves the setting in `localStorage`. The global `body.dark-mode ...` rules in `src/styles.css` lose to Angular's encapsulated component styles, so dark-mode overrides must go in the component CSS as `:host-context(body.dark-mode) .selector`. Selectors that use `[data-theme="dark"]` never match anything.
- **Dark palette** (from the admin pages): page `#1a1a1a`; cards and tables `#2d2d2d`; row hover `#3a3a3a`; borders `#404040`; table text `#ffffff`; accent red `#dc3545`.
- **Admin table action buttons** are 36px icon-only buttons whose label slides out on hover. `organizer.css` has the canonical styles. The action column reserves enough width that hovering doesn't shift the table.
- **Create/Add modals** have Cancel and Create buttons, don't close on backdrop click, and use `backdrop-filter: blur(...)` on the overlay.
