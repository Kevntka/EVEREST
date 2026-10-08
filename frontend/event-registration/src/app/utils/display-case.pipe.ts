import { Pipe, PipeTransform } from '@angular/core';

/** Small words kept lowercase inside a title ("College of Engineering"). */
const MINOR_WORDS = new Set(['of', 'and', 'the', 'in', 'on', 'at', 'for', 'to', 'a', 'an', 'de', 'del', 'ng']);

/**
 * Shows ALL-CAPS text in Title Case in the table lists: names, departments, addresses,
 * gender and year level are saved uppercase ("COLLEGE OF ENGINEERING" -> "College of
 * Engineering", "2ND YEAR" -> "2nd Year"). Text that already has lowercase letters,
 * and "N/A", is shown as typed. Display only; the saved values don't change.
 */
export function displayCase(value: string | null | undefined): string {
  if (!value || /[a-z]/.test(value) || value === 'N/A') return value || '';
  return value.toLowerCase().split(' ')
    .map((word, i) => i > 0 && MINOR_WORDS.has(word)
      ? word
      : word.replace(/(^|[-(\/.'])([a-z])/g, (_, before, letter) => before + letter.toUpperCase()))
    .join(' ');
}

@Pipe({ name: 'displayCase', standalone: true })
export class DisplayCasePipe implements PipeTransform {
  transform(value: string | null | undefined): string {
    return displayCase(value);
  }
}
