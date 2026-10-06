import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { authInterceptor } from './auth.interceptor';
import { csrfInterceptor, resetCsrfToken } from './csrf.interceptor';

const API = 'http://localhost:8000/api';

describe('security interceptors', () => {
  let http: HttpClient;
  let backend: HttpTestingController;
  let navigate: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    resetCsrfToken();
    localStorage.clear();
    navigate = vi.fn();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor, csrfInterceptor])),
        provideHttpClientTesting(),
        { provide: Router, useValue: { navigate } },
      ],
    });
    http = TestBed.inject(HttpClient);
    backend = TestBed.inject(HttpTestingController);
  });

  afterEach(() => backend.verify());

  it('sends the login cookie with API requests', () => {
    http.get(`${API}/events`).subscribe();
    const req = backend.expectOne(`${API}/events`);
    expect(req.request.withCredentials).toBe(true);
    expect(req.request.headers.has('X-CSRF-Token')).toBe(false);
    req.flush({});
  });

  it('fetches the CSRF token once and adds it to POST/PUT/DELETE', () => {
    http.post(`${API}/events/1/enroll`, {}).subscribe();
    backend.expectOne(`${API}/csrf-token`).flush({ csrf_token: 'abc.sig' });
    const first = backend.expectOne(`${API}/events/1/enroll`);
    expect(first.request.headers.get('X-CSRF-Token')).toBe('abc.sig');
    first.flush({});

    http.delete(`${API}/events/1/enroll`).subscribe();
    backend.expectNone(`${API}/csrf-token`);
    expect(backend.expectOne(`${API}/events/1/enroll`).request.headers.get('X-CSRF-Token')).toBe('abc.sig');
  });

  it('gets a new CSRF token and retries once when the backend rejects it', () => {
    let result: unknown;
    http.post(`${API}/change-password`, {}).subscribe((res) => (result = res));
    backend.expectOne(`${API}/csrf-token`).flush({ csrf_token: 'old.sig' });
    backend.expectOne(`${API}/change-password`)
      .flush({ detail: 'CSRF', csrf_failed: true }, { status: 403, statusText: 'Forbidden' });

    backend.expectOne(`${API}/csrf-token`).flush({ csrf_token: 'new.sig' });
    const retry = backend.expectOne(`${API}/change-password`);
    expect(retry.request.headers.get('X-CSRF-Token')).toBe('new.sig');
    retry.flush({ ok: true });
    expect(result).toEqual({ ok: true });
  });

  it('signs the user out when the session has expired (401)', () => {
    localStorage.setItem('userRole', 'student');
    http.get(`${API}/student/my-events`).subscribe({ error: () => {} });
    backend.expectOne(`${API}/student/my-events`).flush({}, { status: 401, statusText: 'Unauthorized' });

    expect(localStorage.getItem('userRole')).toBeNull();
    expect(navigate).toHaveBeenCalledWith(['/login']);
    backend.expectOne(`${API}/csrf-token`).flush({ csrf_token: 't.sig' });
    backend.expectOne(`${API}/logout`).flush({});
  });

  it('does not sign out on a wrong password at login (also 401)', () => {
    localStorage.setItem('userRole', 'student');
    http.post(`${API}/login`, {}).subscribe({ error: () => {} });
    backend.expectOne(`${API}/csrf-token`).flush({ csrf_token: 't.sig' });
    backend.expectOne(`${API}/login`).flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(navigate).not.toHaveBeenCalled();
  });
});
