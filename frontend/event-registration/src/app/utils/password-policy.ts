/**
 * Password strength rules. Used only to RATE a password (the strength bar under
 * confirm-password fields); passwords are not required to meet them.
 */
export const PASSWORD_SYMBOLS = '!@#$%&*_';

export interface PasswordRule {
  /** Full wording of the rule. */
  label: string;
  /** One-line wording. */
  short: string;
  test: (password: string) => boolean;
}

export const PASSWORD_RULES: PasswordRule[] = [
  { label: 'At least 8 characters', short: '8+ characters', test: p => p.length >= 8 },
  { label: 'One uppercase letter (A-Z)', short: 'Uppercase letter', test: p => /[A-Z]/.test(p) },
  { label: 'One lowercase letter (a-z)', short: 'Lowercase letter', test: p => /[a-z]/.test(p) },
  { label: 'One number (0-9)', short: 'Number', test: p => /[0-9]/.test(p) },
  { label: `One symbol (${PASSWORD_SYMBOLS.split('').join(' ')})`, short: `Symbol ${PASSWORD_SYMBOLS}`, test: p => /[!@#$%&*_]/.test(p) },
];

/** Labels of the rules the password doesn't meet yet (empty = strong). */
export function passwordProblems(password: string): string[] {
  return PASSWORD_RULES.filter(rule => !rule.test(password || '')).map(rule => rule.label);
}

export function isStrongPassword(password: string): boolean {
  return passwordProblems(password).length === 0;
}

