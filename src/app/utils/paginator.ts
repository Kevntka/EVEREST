/**
 * Client-side pagination shared by the table pages (10 rows per page).
 * Pass the current (filtered) list to each call; the page is clamped when the
 * list shrinks (e.g. after searching), so no manual reset is needed.
 *
 *   readonly pager = new Paginator();
 *   <tr *ngFor="let x of pager.slice(filteredItems)">
 *   {{ pager.current(filteredItems) }} of {{ pager.totalPages(filteredItems) }}
 */
export class Paginator {
  page = 1;

  constructor(readonly size = 10) {}

  totalPages(items: readonly unknown[]): number {
    return Math.max(1, Math.ceil(items.length / this.size));
  }

  current(items: readonly unknown[]): number {
    return Math.min(Math.max(this.page, 1), this.totalPages(items));
  }

  slice<T>(items: readonly T[]): T[] {
    const page = this.current(items);
    return items.slice((page - 1) * this.size, page * this.size);
  }

  isFirst(items: readonly unknown[]): boolean {
    return this.current(items) <= 1;
  }

  isLast(items: readonly unknown[]): boolean {
    return this.current(items) >= this.totalPages(items);
  }

  prev(items: readonly unknown[]): void {
    this.page = Math.max(1, this.current(items) - 1);
  }

  next(items: readonly unknown[]): void {
    this.page = Math.min(this.totalPages(items), this.current(items) + 1);
  }
}
