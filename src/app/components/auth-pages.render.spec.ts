import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Type } from '@angular/core';
import { Login } from './login/login';
import { Register } from './register/register';
import { RegisterStudent } from './register-student/register-student';
import { RegisterParticipant } from './register-participant/register-participant';
import { ForgotPassword } from './forgot-password/forgot-password';
import { CheckEmail } from './check-email/check-email';
import { ResetPassword } from './reset-password/reset-password';

const pages: [string, Type<unknown>, string][] = [
  ['login', Login, '.login-container'],
  ['register', Register, '.register-container'],
  ['register-student', RegisterStudent, '.register-container'],
  ['register-participant', RegisterParticipant, '.register-container'],
  ['forgot-password', ForgotPassword, '.forgot-password-container'],
  ['check-email', CheckEmail, '.check-email-container'],
  ['reset-password', ResetPassword, '.reset-password-container'],
];

describe('auth pages render their card', () => {
  for (const darkMode of [false, true]) {
    for (const [name, component, selector] of pages) {
      it(`${name} (${darkMode ? 'dark' : 'light'})`, async () => {
        localStorage.setItem('darkMode', String(darkMode));
        (window as any).alert = () => {};
        TestBed.configureTestingModule({
          imports: [component],
          // Catch-all route so redirects in ngOnInit (e.g. reset-password without a token) don't throw
          providers: [provideRouter([{ path: '**', children: [] }]), provideHttpClient(), provideHttpClientTesting()],
        });
        const fixture = TestBed.createComponent(component);
        fixture.detectChanges();
        await fixture.whenStable();
        const el: HTMLElement = fixture.nativeElement;
        expect(el.querySelector('.dark-mode-toggle')).not.toBeNull();
        expect(el.querySelector(selector)).not.toBeNull();
      });
    }
  }
});
