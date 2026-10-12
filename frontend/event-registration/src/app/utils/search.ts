/**
 * The search rule every search bar uses: case-insensitive, ignores spaces at the start
 * and end and extra spaces between words.
 *   matchesSearch('ANA  SANTOS', ' ana santos ') -> true
 *   matchesSearch('Ben Cruz', '')                -> true (an empty search matches everything)
 */
export function normalizeSearch(text: string | null | undefined): string {
  return (text || '').trim().replace(/\s+/g, ' ').toLowerCase();
}

export function matchesSearch(text: string | null | undefined, query: string | null | undefined): boolean {
  return normalizeSearch(text).includes(normalizeSearch(query));
}
