import { isStrongPassword, passwordProblems } from './password-policy';

// Same cases as the backend's validate_password_strength() tests; the two must agree.
describe('password policy', () => {
  it.each([
    ['Str0ng!pass', true],
    ['N3w_Strong', true],
    ['Aa1!aaaa', true],
    ['alllowercase1!', false],
    ['ALLUPPER1!', false],
    ['NoNumber!!', false],
    ['NoSymbol123', false],
    ['Passw0rd^^', true],  // any symbol counts
    ['Passw0rd.', true],
    ['Passw0rd-', true],
    ['Passw0rd ', false],  // a space isn't a symbol
    ['Passw0rdñ', false],  // nor is a letter like ñ
    ['Aa1!', false],
    ['', false],
  ])('%s -> strong: %s', (password, strong) => {
    expect(isStrongPassword(password)).toBe(strong);
  });

  it('lists every missing rule', () => {
    expect(passwordProblems('abc')).toEqual([
      'At least 8 characters',
      'One uppercase letter (A-Z)',
      'One number (0-9)',
      'One symbol (e.g. ! @ # $ % ^ & *)',
    ]);
  });
});
