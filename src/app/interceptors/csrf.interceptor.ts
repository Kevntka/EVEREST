import { HttpInterceptorFn, HttpRequest, HttpHandlerFn, HttpEvent } from '@angular/common/http';
import { inject } from '@angular/core';
import { Observable, from, switchMap, catchError, throwError } from 'rxjs';
import { HttpClient } from '@angular/common/http';

// CSRF token storage
let csrfToken: string | null = null;

/**
 * Get CSRF token from cookie
 */
function getCsrfTokenFromCookie(): string | null {
  const name = 'csrf_token=';
  const decodedCookie = decodeURIComponent(document.cookie);
  const cookieArray = decodedCookie.split(';');
  
  for (let cookie of cookieArray) {
    cookie = cookie.trim();
    if (cookie.indexOf(name) === 0) {
      return cookie.substring(name.length);
    }
  }
  return null;
}

/**
 * Fetch CSRF token from backend
 */
async function fetchCsrfToken(http: HttpClient): Promise<string> {
  try {
    const response: any = await http.get('http://localhost:8000/api/csrf-token', {
      withCredentials: true
    }).toPromise();
    
    if (response && response.csrf_token) {
      const token: string = response.csrf_token;
      csrfToken = token;
      return token;
    }
    
    throw new Error('No CSRF token in response');
  } catch (error) {
    console.error('Failed to fetch CSRF token:', error);
    throw error;
  }
}

/**
 * HTTP Interceptor to automatically add CSRF token to requests
 */
export const csrfInterceptor: HttpInterceptorFn = (
  req: HttpRequest<any>,
  next: HttpHandlerFn
): Observable<HttpEvent<any>> => {
  const http = inject(HttpClient);
  
  // Skip CSRF for safe methods (GET, HEAD, OPTIONS)
  if (req.method === 'GET' || req.method === 'HEAD' || req.method === 'OPTIONS') {
    return next(req);
  }
  
  // Skip CSRF for external URLs (not our API)
  if (!req.url.includes('localhost:8000/api')) {
    return next(req);
  }
  
  // Skip CSRF for login endpoint (token will be set after login)
  if (req.url.includes('/api/login')) {
    return next(req);
  }
  
  // Get token from cookie first
  let token: string | null = getCsrfTokenFromCookie();
  
  if (!token && csrfToken) {
    token = csrfToken;
  }
  
  // If no token yet, fetch it first
  if (!token) {
    return from(fetchCsrfToken(http)).pipe(
      switchMap((fetchedToken: string) => {
        // Clone request and add CSRF token
        const clonedReq = req.clone({
          withCredentials: true,
          headers: req.headers.set('X-CSRF-Token', fetchedToken)
        });
        return next(clonedReq);
      }),
      catchError((error) => {
        console.error('CSRF interceptor error:', error);
        return throwError(() => error);
      })
    );
  }
  
  // Clone request and add CSRF token (token is guaranteed non-null here)
  const clonedReq = req.clone({
    withCredentials: true,
    headers: req.headers.set('X-CSRF-Token', token)
  });
  
  return next(clonedReq);
};
