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

/** The browser's local date as "YYYY-MM-DD", the format <input type="date"> uses. */
export function localToday(now = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** The browser's local time as "HH:MM", the format <input type="time"> uses. */
export function localTime(now = new Date()): string {
  return now.toTimeString().slice(0, 5);
}

/**
 * Earliest date a date picker allows: today, so past days can't be picked. When editing,
 * a past date the event already has stays pickable, so the form still opens and saves.
 */
export function minPickableDate(current?: string | null, now = new Date()): string {
  const today = localToday(now);
  return current && current < today ? current : today;
}

export interface EventSchedule {
  date: string;              // YYYY-MM-DD
  endTime: string;           // HH:MM
  registrationStart: string; // YYYY-MM-DD
  registrationEnd: string;   // YYYY-MM-DD
}

/**
 * Message for a schedule that is already in the past, or null. A new event must end in the
 * future (otherwise it would be created already Closed). When editing (`original` given),
 * only the parts that changed are checked, so an event that already happened can still be
 * edited, e.g. to fix a typo. The backend checks the same rules.
 */
export function pastScheduleError(s: EventSchedule, original: EventSchedule | null, now = new Date()): string | null {
  const today = localToday(now);
  const changed = (key: keyof EventSchedule) => !original || s[key] !== original[key];
  // "YYYY-MM-DDTHH:MM" strings compare correctly as text
  if ((changed('date') || changed('endTime')) && `${s.date}T${s.endTime}` <= `${today}T${localTime(now)}`) {
    return "This event's date and end time have already passed. Please choose a later date or time.";
  }
  if (changed('registrationStart') && s.registrationStart < today) {
    return 'The registration start date has already passed. Please choose today or a later date.';
  }
  if (changed('registrationEnd') && s.registrationEnd < today) {
    return 'The registration end date has already passed. Please choose today or a later date.';
  }
  return null;
}
