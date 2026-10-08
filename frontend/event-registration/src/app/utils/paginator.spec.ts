import { Paginator } from './paginator';

describe('Paginator', () => {
  const items = Array.from({ length: 23 }, (_, i) => i + 1);

  it('shows 10 per page and counts pages', () => {
    const p = new Paginator();
    expect(p.totalPages(items)).toBe(3);
    expect(p.slice(items)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    expect(p.isFirst(items)).toBe(true);
  });

  it('moves between pages and stops at the ends', () => {
    const p = new Paginator();
    p.next(items); p.next(items); p.next(items);
    expect(p.current(items)).toBe(3);
    expect(p.slice(items)).toEqual([21, 22, 23]);
    expect(p.isLast(items)).toBe(true);
    p.prev(items);
    expect(p.current(items)).toBe(2);
  });

  it('clamps to the last page when the list shrinks (e.g. after a search)', () => {
    const p = new Paginator();
    p.next(items); p.next(items);
    expect(p.current([1, 2, 3])).toBe(1);
    expect(p.slice([1, 2, 3])).toEqual([1, 2, 3]);
  });

  it('treats an empty list as 1 of 1', () => {
    const p = new Paginator();
    expect(`${p.current([])} of ${p.totalPages([])}`).toBe('1 of 1');
    expect(p.slice([])).toEqual([]);
  });
});
