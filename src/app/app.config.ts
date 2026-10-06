import { ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { changeDetectionInterceptor } from './interceptors/change-detection.interceptor';
import { authInterceptor } from './interceptors/auth.interceptor';
import { csrfInterceptor } from './interceptors/csrf.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(
      withFetch(),  // Use fetch API for better compatibility
      // auth: send the login cookie, sign out on 401; csrf: X-CSRF-Token on POST/PUT/DELETE
      withInterceptors([changeDetectionInterceptor, authInterceptor, csrfInterceptor])
    )
  ]
};
