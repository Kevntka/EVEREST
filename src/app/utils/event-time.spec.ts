import { formatTime, formatTimeRange } from './event-time';

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
});
