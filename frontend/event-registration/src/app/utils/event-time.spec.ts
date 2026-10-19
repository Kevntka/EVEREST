import { formatTime, formatTimeRange, localToday, minPickableDate, pastScheduleError } from './event-time';

describe('event-time', () => {
  it('formats 24-hour times as 12-hour', () => {
    expect(formatTime('00:05:00')).toBe('12:05 AM');
    expect(formatTime('12:00:00')).toBe('12:00 PM');
    expect(formatTime('14:30:00')).toBe('2:30 PM');
    expect(formatTime('09:15')).toBe('9:15 AM');
    expect(formatTime(null)).toBe('TBA');
  });

  it('formats a start-end range, or just the start when there is no end', () => {
    expect(formatTimeRange('08:00:00', '17:00:00')).toBe('8:00 AM - 5:00 PM');
    expect(formatTimeRange('08:00:00', null)).toBe('8:00 AM');
    expect(formatTimeRange(null, '17:00:00')).toBe('TBA');
  });

  describe('past dates', () => {
    const now = new Date(2026, 9, 19, 11, 30); // Oct 19, 2026, 11:30 AM local time
    const future = { date: '2026-10-25', endTime: '17:00', registrationStart: '2026-10-19', registrationEnd: '2026-10-24' };

    it('uses the local date', () => {
      expect(localToday(now)).toBe('2026-10-19');
    });

    it('lets date pickers start today, or at a past date the event already has', () => {
      expect(minPickableDate('', now)).toBe('2026-10-19');
      expect(minPickableDate('2026-11-01', now)).toBe('2026-10-19');
      expect(minPickableDate('2026-10-01', now)).toBe('2026-10-01');
    });

    it('accepts a new event that ends later, even later today', () => {
      expect(pastScheduleError(future, null, now)).toBeNull();
      expect(pastScheduleError({ ...future, date: '2026-10-19', endTime: '11:31' }, null, now)).toBeNull();
    });

    it('rejects a new event that already ended (past day, or earlier today)', () => {
      expect(pastScheduleError({ ...future, date: '2026-10-18' }, null, now)).toContain('already passed');
      expect(pastScheduleError({ ...future, date: '2026-10-19', endTime: '11:30' }, null, now)).toContain('already passed');
    });

    it('rejects a new registration period that already started or ended', () => {
      expect(pastScheduleError({ ...future, registrationStart: '2026-10-18' }, null, now)).toContain('registration start');
      expect(pastScheduleError({ ...future, registrationEnd: '2026-10-18' }, null, now)).toContain('registration end');
    });

    it('lets a past event be edited as long as its dates and times stay the same', () => {
      const past = { date: '2026-10-01', endTime: '17:00', registrationStart: '2026-09-20', registrationEnd: '2026-09-30' };
      expect(pastScheduleError(past, past, now)).toBeNull();
      expect(pastScheduleError({ ...past, endTime: '18:00' }, past, now)).toContain('already passed');
      expect(pastScheduleError({ ...past, date: '2026-10-30', registrationEnd: '2026-10-29' }, past, now)).toBeNull();
    });
  });
});
