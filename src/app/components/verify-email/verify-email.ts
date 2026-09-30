import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize } from 'rxjs';
import { ThemeService } from '../../services/theme.service';
import { DialogService } from '../../services/dialog.service';

/**
 * Enter the 6-digit code emailed after student/participant registration.
 * Reached with ?email=... (and &resend=1 from login, to send a fresh code).
 */
@Component({
  selector: 'app-verify-email',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './verify-email.html',
  styleUrls: ['../forgot-password/forgot-password.css', './verify-email.css'],
})
export class VerifyEmail implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private dialog = inject(DialogService);
  readonly themeService = inject(ThemeService);

  email = '';
  code = '';
  isSaving = false;
  /** Seconds until "Resend code" is allowed again (signal so the countdown renders when zoneless). */
  readonly resendIn = signal(0);
  private timer: ReturnType<typeof setInterval> | null = null;

  ngOnInit(): void {
    const params = this.route.snapshot.queryParamMap;
    this.email = (params.get('email') || '').trim().toLowerCase();
    if (!this.email) {
      this.router.navigate(['/register']);
      return;
    }
    if (params.get('resend') === '1') {
      this.resendCode();
    } else {
      this.startCooldown(60); // a code was just sent at registration
    }
  }

  ngOnDestroy(): void {
    this.stopTimer();
  }

  toggleDarkMode(): void {
    this.themeService.toggleDarkMode();
  }

  /** Keep only digits, max 6. */
  onCodeInput(value: string): void {
    this.code = (value || '').replace(/\D/g, '').slice(0, 6);
  }

  verify(): void {
    if (this.code.length !== 6) {
      this.dialog.error('Check your input', 'Please enter the 6-digit code from your email.');
      return;
    }
    const formData = new FormData();
    formData.append('email', this.email);
    formData.append('code', this.code);

    this.isSaving = true;
    this.http.post<any>('http://localhost:8000/api/verify-email', formData)
      .pipe(finalize(() => (this.isSaving = false)))
      .subscribe({
        next: (response) => {
          this.dialog.success('Verified!', response.message || 'Your email has been verified. You can now log in.');
          this.router.navigate(['/login']);
        },
        error: (error) => {
          this.code = '';
          this.dialog.error('Verification failed', error.error?.detail || 'Please try again.');
        }
      });
  }

  resendCode(): void {
    if (this.resendIn() > 0) return;
    const formData = new FormData();
    formData.append('email', this.email);

    this.http.post<any>('http://localhost:8000/api/resend-verification', formData)
      .subscribe({
        next: (response) => {
          this.dialog.success('Code Sent!', `A new verification code was sent to ${this.email}.
If you don't see it in your inbox, check your Spam folder.`);
          this.startCooldown(response.retry_after || 60);
        },
        error: (error) => {
          if (error.status === 429 && error.error?.retry_after) {
            // A code was sent moments ago (e.g. at registration); just show the countdown
            this.startCooldown(error.error.retry_after);
            return;
          } else if (error.status === 400) {
            // already verified
            this.dialog.success('Success!', error.error?.detail || 'Your email is already verified.');
            this.router.navigate(['/login']);
            return;
          }
          this.dialog.error('Could not send code', error.error?.detail || 'Please try again later.');
        }
      });
  }

  goToLogin(): void {
    this.router.navigate(['/login']);
  }

  private startCooldown(seconds: number): void {
    this.stopTimer();
    this.resendIn.set(seconds);
    this.timer = setInterval(() => {
      this.resendIn.update(s => s - 1);
      if (this.resendIn() <= 0) this.stopTimer();
    }, 1000);
  }

  private stopTimer(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}
