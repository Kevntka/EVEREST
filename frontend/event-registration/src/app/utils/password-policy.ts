/**
 * Password rules. New passwords (registration and Reset / Set New Password) must meet
 * all of them; the backend checks the same rules (security/validation.py: new_password).
 * Login doesn't check them, so older accounts with weaker passwords can still sign in.
 * The strength bar under confirm-password fields shows how many are met.
 */
/** Examples shown to the user; ANY symbol counts (anything that isn't a letter, number, or space). */
export const PASSWORD_SYMBOL_EXAMPLES = '! @ # $ % ^ & *';

/** True if the password has a symbol: a character that isn't a letter (any language), a number, or a space. */
export function hasSymbol(password: string): boolean {
  return /[^\p{L}\p{N}\s]/u.test(password);
}

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
  { label: `One symbol (e.g. ${PASSWORD_SYMBOL_EXAMPLES})`, short: 'Symbol', test: hasSymbol },
];

/** Labels of the rules the password doesn't meet yet (empty = strong). */
export function passwordProblems(password: string): string[] {
  return PASSWORD_RULES.filter(rule => !rule.test(password || '')).map(rule => rule.label);
}

export function isStrongPassword(password: string): boolean {
  return passwordProblems(password).length === 0;
}

/** Shown when a new password misses a rule (same wording as the backend's error). */
export const PASSWORD_REQUIREMENT_MESSAGE =
  `Password must have at least 8 characters, an uppercase letter, a lowercase letter, a number, and a symbol (e.g. ${PASSWORD_SYMBOL_EXAMPLES}).`;

