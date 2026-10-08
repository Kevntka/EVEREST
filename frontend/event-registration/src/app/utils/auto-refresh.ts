import { DestroyRef, inject } from '@angular/core';

/** How often the event pages re-fetch, so Open / Full / Closed / Upcoming change without a page reload. */
export const AUTO_REFRESH_MS = 10_000;

/**
 * Calls `refresh` every AUTO_REFRESH_MS while the page is open (skipped while the
 * browser tab is hidden) and stops when the component is destroyed. Call it from a
 * field initializer so it runs in an injection context:
 *
 *   private autoRefresh = autoRefresh(() => this.loadEvents(true));
 *
 * The refresh should be silent (no loading spinner, no error dialogs). The HTTP
 * change-detection interceptor updates the view when the response arrives.
 */
export function autoRefresh(refresh: () => void, ms = AUTO_REFRESH_MS): void {
  const timer = setInterval(() => {
    if (!document.hidden) refresh();
  }, ms);
  inject(DestroyRef).onDestroy(() => clearInterval(timer));
}
