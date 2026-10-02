/**
 * Event times come from the API as "HH:MM:SS" (or null).
 *   formatTime('14:30:00')                 -> '2:30 PM'
 *   formatTimeRange('08:00:00', '17:00:00') -> '8:00 AM - 5:00 PM'
 */
export function formatTime(time: string | null | undefined): string {
  if (!time) return 'TBA';
  const [h, m] = time.split(':');
  const hour = Number(h);
  if (Number.isNaN(hour) || m === undefined) return 'TBA';
  return `${hour % 12 || 12}:${m.slice(0, 2)} ${hour >= 12 ? 'PM' : 'AM'}`;
}

export function formatTimeRange(start: string | null | undefined, end: string | null | undefined): string {
  if (!start) return 'TBA';
  return end ? `${formatTime(start)} - ${formatTime(end)}` : formatTime(start);
}
