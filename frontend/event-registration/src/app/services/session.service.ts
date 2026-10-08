import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';

/** Everything login.ts saves in localStorage about the logged-in user. */
const SESSION_KEYS = ['userToken', 'userRole', 'userName', 'userId', 'userEmail', 'organizerId', 'organizerName'];

/**
 * The login session. The real proof of login is the HTTP-only access_token cookie,
 * which only the backend can clear, so signing out must call POST /api/logout as
 * well as clearing localStorage. Used by the Sign Out item on every page and by
 * the auth interceptor when the backend answers 401 (session expired).
 */
@Injectable({ providedIn: 'root' })
export class SessionService {
  private http = inject(HttpClient);
  private router = inject(Router);

  /** Forget the user in this browser (localStorage) without contacting the backend. */
  clear(): void {
    SESSION_KEYS.forEach((key) => localStorage.removeItem(key));
  }

  /** Sign out: delete the login cookie on the backend, clear localStorage, go to Login. */
  signOut(): void {
    this.clear();
    this.http.post('http://localhost:8000/api/logout', {}).subscribe({ error: () => {} });
    this.router.navigate(['/login']);
  }
}
