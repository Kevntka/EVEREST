import { HttpInterceptorFn } from '@angular/common/http';
import { ApplicationRef, inject } from '@angular/core';
import { finalize } from 'rxjs';

/**
 * The app is zoneless, so views don't refresh on their own when an HTTP
 * response arrives (and ApplicationRef.tick() skips views not marked dirty).
 * finalize runs after the component's subscribe callbacks (next/error);
 * marking the root components for check schedules a refresh of the whole
 * default-strategy view tree, so whatever those callbacks assigned renders.
 */
export const changeDetectionInterceptor: HttpInterceptorFn = (req, next) => {
  const appRef = inject(ApplicationRef);
  return next(req).pipe(
    finalize(() => appRef.components.forEach((c) => c.changeDetectorRef.markForCheck()))
  );
};
