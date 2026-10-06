import { HttpClient, HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Observable, catchError, map, shareReplay, switchMap, throwError } from 'rxjs';

export const API_ORIGIN = 'http://localhost:8000';
const SAFE_METHODS = ['GET', 'HEAD', 'OPTIONS'];

let token$: Observable<string> | null = null;

/** GET /api/csrf-token once and share the answer with every request waiting for it. */
function csrfToken(http: HttpClient): Observable<string> {
  token$ ??= http
    .get<{ csrf_token: string }>(`${API_ORIGIN}/api/csrf-token`, { withCredentials: true })
    .pipe(
      map((res) => res.csrf_token),
      catchError((error) => {
        token$ = null; // let the next request try again
        return throwError(() => error);
      }),
      shareReplay(1),
    );
  return token$;
}

/** For tests: forget the cached token. */
export function resetCsrfToken(): void {
  token$ = null;
}

/**
 * CSRF protection (backend: security/csrf.py). Every POST/PUT/PATCH/DELETE to the API
 * carries the X-CSRF-Token header with the token from GET /api/csrf-token. If the
 * backend rejects it (403 with csrf_failed, e.g. the server restarted with a new
 * secret), the token is fetched again and the request is retried once.
 */
export const csrfInterceptor: HttpInterceptorFn = (req, next) => {
  if (SAFE_METHODS.includes(req.method) || !req.url.startsWith(`${API_ORIGIN}/api`)) {
    return next(req);
  }
  const http = inject(HttpClient);
  const withToken = (token: string): HttpRequest<unknown> =>
    req.clone({ withCredentials: true, setHeaders: { 'X-CSRF-Token': token } });

  return csrfToken(http).pipe(
    switchMap((token) => next(withToken(token))),
    catchError((error) => {
      if (!(error instanceof HttpErrorResponse) || error.status !== 403 || !error.error?.csrf_failed) {
        return throwError(() => error);
      }
      token$ = null;
      return csrfToken(http).pipe(switchMap((token) => next(withToken(token))));
    }),
  );
};
