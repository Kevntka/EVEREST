/**
 * Enrolling opens on the event's registration start date; events without one open on
 * the event date. Until then an event is "upcoming" and can't be enrolled in.
 * Dates are YYYY-MM-DD strings, which compare correctly as text.
 */

/** Today as YYYY-MM-DD in local time. */
export function todayString(now = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

/** The date enrolling opens ('' when the event has neither date). */
export function registrationOpensOn(registrationStart?: string | null, eventDate?: string | null): string {
  return registrationStart || eventDate || '';
}

export function isRegistrationOpen(opensOn: string, now = new Date()): boolean {
  return !opensOn || opensOn <= todayString(now);
}

/** Past the registration end date (the last day to enroll); no end date = never. */
export function isRegistrationOver(closesOn?: string | null, now = new Date()): boolean {
  return !!closesOn && closesOn < todayString(now);
}

/** '2026-10-05' -> 'Oct 5, 2026'. */
export function formatShortDate(value: string): string {
  const [y, m, d] = (value || '').split('-').map(Number);
  if (!y || !m || !d) return value || '';
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/**
 * The status shown on badges: 'closed'/'cancelled' as stored; an open event is
 * 'upcoming' before registration starts, 'closed' once registration has ended,
 * 'full' with no slots left, else 'open'.
 */
export function displayStatus(status: string, opensOn: string, enrolled: number, capacity: number | null,
                              closesOn?: string | null): string {
  const stored = (status || '').toLowerCase();
  if (stored !== 'open') return stored;
  if (!isRegistrationOpen(opensOn)) return 'upcoming';
  if (isRegistrationOver(closesOn)) return 'closed';
  if (capacity != null && enrolled >= capacity) return 'full';
  return 'open';
}
