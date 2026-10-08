import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { SessionService } from '../services/session.service';
import { API_ORIGIN } from './csrf.interceptor';

/** Endpoints where 401 means "wrong password", not "session expired". */
const LOGIN_URL = `${API_ORIGIN}/api/login`;

/**
 * Access control support. The backend checks the HTTP-only login cookie on every
 * protected endpoint, so every API request is sent with credentials (cookies).
 * When the backend says the session is no longer valid (401: expired, signed out,
 * password changed, account deleted), the user is signed out here too, so the
 * localStorage-based route guards don't keep showing pages the API refuses.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith(`${API_ORIGIN}/api`)) {
    return next(req);
  }
  const session = inject(SessionService);
  return next(req.clone({ withCredentials: true })).pipe(
    catchError((error) => {
      if (error instanceof HttpErrorResponse && error.status === 401
          && req.url !== LOGIN_URL && localStorage.getItem('userRole')) {
        session.signOut();
      }
      return throwError(() => error);
    }),
  );
};
