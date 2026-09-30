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

There are no backend tests. Configuration comes from `backend/.env` (loaded with python-dotenv): `DATABASE_URL`, `JWT_SECRET_KEY`, `SMTP_*`, `EMAIL_ENABLED`, `BREVO_API_KEY`, and `RECAPTCHA_SECRET_KEY`. All mail goes through `_send()` in `services/email_service.py`. It uses Brevo's HTTPS API when `BREVO_API_KEY` is set and SMTP otherwise. The campus network ("BatStateU ICT") blocks every outbound SMTP port (587, 465, 2525), so SMTP only works on other networks. The schema is in `backend/database/schema.sql`.

## Architecture

**Roles and pages.** There are four roles: `admin`, `organizer`, `student`, and `participant`. Each role has its own set of standalone page components under `src/app/components/`:
- Admin: `dashboard`, `organizer`, `students`, `participants`
- Organizer: `organizer-dashboard`, `organizer-events`, `organizer-attendance`
- Student and participant: `student-dashboard`, `student-profile` (student only), `my-events`, `event-details`. `my-events` reuses `student-dashboard.css` and loads data from `GET /api/student/my-events`, which uses the login cookie.

Each page component contains its own sidebar, top bar, and modals. There is no shared layout component, so a UI change to one page usually has to be repeated on its sibling pages.

**Change detection.** The app is zoneless: there's no zone.js, so views don't update on their own after async work. For HTTP responses, `interceptors/change-detection.interceptor.ts` (registered in `app.config.ts`) calls `markForCheck()` on the root components after each request's subscribe callbacks. Don't switch this to `ApplicationRef.tick()`: in zoneless mode, `tick()` skips views that aren't marked dirty. Its spec is the regression test. Other async sources, such as `setTimeout` or third-party callbacks, still need `ChangeDetectorRef.detectChanges()` or signals. Some components also call `cdr.detectChanges()` after HTTP responses. That code predates the interceptor and is now redundant, but it does no harm.

**API calls.** Components call `HttpClient` directly with hardcoded `http://localhost:8000/api/...` URLs. There is no API service layer. The backend's CORS setting only allows `localhost:4200`. Most endpoints take `multipart/form-data` (FastAPI `Form(...)`), so the frontend sends `FormData`.

**Authentication**
- `POST /api/login` verifies the reCAPTCHA token and sets an HTTP-only `access_token` JWT cookie.
- The frontend separately stores `userRole`, `userName`, `userId`, and, for organizers, `organizerId`/`organizerName` in `localStorage`.
- The route guards in `guards/auth.guard.ts` read only `localStorage`.
- Almost no backend endpoints check authentication. For example, `POST`/`PUT /api/events` trust the `organizer_id` form field sent by the frontend. The exceptions are change-password and `GET`/`PUT /api/student/profile`: they identify the user with `current_user_id(request)` in `routes_db.py`, which reads the login cookie. The frontend must call them with `{ withCredentials: true }`.
- `interceptors/csrf.interceptor.ts` and `backend/auth/csrf_protection.py` exist, but the interceptor is commented out in `app.config.ts`.
- The reCAPTCHA site key is Google's test key.

**Data model** (`backend/models/user.py`, mirroring `schema.sql`)
- `users` holds identity, including the `role` string. `user_roles` holds per-role details: department, employment ID, and contact number.
- `events.user_role_id` references `user_roles.id`, not `users.id`. To link an event to an organizer, look up the organizer's `user_roles` row.
- `registrations.user_id` and `events.user_role_id` have **no** `ON DELETE CASCADE`. The delete endpoints for students, participants, and organizers remove those rows first; deleting an organizer also deletes their events. `registrations` cascade from `events`, and `attendees` cascade from `registrations`.
- **Email verification.** Student and participant sign-ups are not created in `users` until verified. Registering saves the details (with the bcrypt password hash) and a SHA-256 hash of a 6-digit code in `pending_registrations`. `POST /api/verify-email` checks the code and only then creates the `users` and `user_roles` rows and deletes the pending row. Codes expire after 15 minutes and allow 5 attempts; resending is limited to once per 60 seconds, and pending rows older than 24 hours are purged. Unverified sign-ups therefore never appear in admin lists or counts. Login with a pending email and the correct password returns 403 with `verification_required`, and the frontend redirects to `/verify-email?email=...&resend=1`. Admins and organizers don't use this. `users.is_active` is a BOOLEAN column.
- **Password strength is rated, not required** (product decision). `<app-password-checklist>`, placed under each confirm-password field, shows a strength bar: Weak, Fair, Good, or Strong. The rating counts how many rules in `utils/password-policy.ts` a password meets: at least 8 characters, an uppercase letter, a lowercase letter, a number, and one of `!@#$%&*_`. The backend's `require_password()` only rejects empty passwords, in registration, change password, and reset password. Generated organizer passwords come from `generate_strong_password()`.
- `user_roles` also holds the profile fields `gender`, `year_level`, and `program`, edited on the student Profile page.
- Some endpoints use ORM models; others (events) use raw `text()` SQL.
- Event dates are serialized as `YYYY-MM-DD` strings, and the frontend compares them as strings.
- Event cover photos are stored in the database: the bytes go in `events.cover_photo_data` (BYTEA) and the MIME type in `cover_photo_type`, with a 5 MB limit. They're served by `GET /api/events/{id}/cover`. `events.cover_photo` holds that URL path, and the frontend prefixes it with `http://localhost:8000`. `backend/uploads/` and the `/uploads` static mount are leftovers from the old file-based storage.

## Styling conventions

- **Dark mode.** `ThemeService` toggles `body.dark-mode` and saves the setting in `localStorage`. The global `body.dark-mode ...` rules in `src/styles.css` lose to Angular's encapsulated component styles, so dark-mode overrides must go in the component CSS as `:host-context(body.dark-mode) .selector`. Selectors that use `[data-theme="dark"]` never match anything.
- **Primary buttons** everywhere (Add, Create, Log In, Register, Enroll, View Details, dialog OK, and so on) use the Add Organizer red: `#dc3545`, `#c82333` on hover, and `#f5c6cb` when disabled. Secondary buttons (Cancel, Edit/View in admin tables, Present/Not Recorded) stay gray or tinted.
- **Dark palette** (from the admin pages): page `#1a1a1a`; cards and tables `#2d2d2d`; row hover `#3a3a3a`; borders `#404040`; table text `#ffffff`; accent red `#dc3545`.
- **Table pages** (admin Dashboard, Organizer, Students, Participants, Organizer Events, Attendance, and My Events) share one layout. The page content has the `page-fill` class and the table sits in a `.table-scroll` wrapper inside `.table-container`; the shared rules are in `styles.css`. The card fills the screen, rows scroll under a pinned header row, and the pagination stays at the bottom. Empty and loading messages go in a `<div class="table-empty">` after the `</table>` so they center in the table area. Rows are paged 10 at a time with `Paginator` (`utils/paginator.ts`): `*ngFor="let x of pager.slice(list)"`.
- **Admin table action buttons** are 36px icon-only buttons whose label slides out on hover. `organizer.css` has the canonical styles. The action column reserves enough width that hovering doesn't shift the table.
- **Create/Add modals** have Cancel and Create buttons, don't close on backdrop click, and use `backdrop-filter: blur(...)` on the overlay.
- **Confirmations and notices.** Use `DialogService` (`services/dialog.service.ts`) instead of `window.confirm` or `alert`. It is rendered once by `<app-dialog-host>` in `app.html`. `await dialog.confirm('Warning', 'Are you sure you want to delete this ...?')` is the only dialog with buttons (Cancel and OK), and it resolves to a boolean. `dialog.success('Success!' | 'Deleted!', ...)`, `dialog.warning(...)`, and `dialog.error(...)` are notices with no buttons: they stay open until the user clicks anywhere or presses Escape. Messages may contain `\n`. Every page uses it; there are no `alert()` or `confirm()` calls left.
