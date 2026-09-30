import { ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { changeDetectionInterceptor } from './interceptors/change-detection.interceptor';
// import { csrfInterceptor } from './interceptors/csrf.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(
      withFetch(),  // Use fetch API for better compatibility
      withInterceptors([changeDetectionInterceptor])
      // withInterceptors([csrfInterceptor])  // Temporarily disabled
    )
  ]
};
