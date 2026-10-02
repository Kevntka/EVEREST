import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, Router } from '@angular/router';
import { ThemeService } from '../../services/theme.service';
import { DialogService } from '../../services/dialog.service';

/**
 * Account verification for student/participant sign-ups (no code to type).
 * - ?email=...            "Check your email": a Verify Account link was sent (&resend=1 from login sends a fresh one)
 * - ?token=...            opened from that link: verifies right away, then goes to Login (or shows why it failed)
 */
@Component({
  selector: 'app-verify-email',
  standalone: true,
  imports: [CommonModule],
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
  /** 'sent': waiting for the user to open the link; the others come from opening it. */
  readonly state = signal<'sent' | 'verifying' | 'failed'>('sent');
  readonly message = signal('');
  /** Seconds until "Resend link" is allowed again (signal so the countdown renders when zoneless). */
  readonly resendIn = signal(0);
  private timer: ReturnType<typeof setInterval> | null = null;

  ngOnInit(): void {
    const params = this.route.snapshot.queryParamMap;
    const token = params.get('token');
    if (token) {
      this.verify(token);
      return;
    }

    this.email = (params.get('email') || '').trim().toLowerCase();
    if (!this.email) {
      this.router.navigate(['/register']);
      return;
    }
    if (params.get('resend') === '1') {
      this.resendLink();
    } else {
      this.startCooldown(60); // a link was just sent at registration
    }
  }

  ngOnDestroy(): void {
    this.stopTimer();
  }

  toggleDarkMode(): void {
    this.themeService.toggleDarkMode();
  }

  private verify(token: string): void {
    const formData = new FormData();
    formData.append('token', token);

    this.state.set('verifying');
    this.http.post<any>('http://localhost:8000/api/verify-email', formData)
      .subscribe({
        next: (response) => {
          this.dialog.success('Verified!', response.message || 'Your account has been verified. You can now log in.');
          this.router.navigate(['/login']);
        },
        error: (error) => {
          // An expired link still tells us the email, so a new link can be sent from here
          this.email = error.error?.email || '';
          this.message.set(error.error?.detail || 'We could not verify your account. Please try again.');
          this.state.set('failed');
        }
      });
  }

  resendLink(): void {
    if (this.resendIn() > 0 || !this.email) return;
    const formData = new FormData();
    formData.append('email', this.email);

    this.http.post<any>('http://localhost:8000/api/resend-verification', formData)
      .subscribe({
        next: (response) => {
          this.dialog.success('Link Sent!', `A new verification link was sent to ${this.email}.
If you don't see it in your inbox, check your Spam folder.`);
          this.state.set('sent');
          this.startCooldown(response.retry_after || 60);
        },
        error: (error) => {
          if (error.status === 429 && error.error?.retry_after) {
            // A link was sent moments ago (e.g. at registration); just show the countdown
            this.state.set('sent');
            this.startCooldown(error.error.retry_after);
            return;
          } else if (error.status === 400) {
            // already verified
            this.dialog.success('Success!', error.error?.detail || 'Your account is already verified.');
            this.router.navigate(['/login']);
            return;
          }
          this.dialog.error('Could not send link', error.error?.detail || 'Please try again later.');
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
