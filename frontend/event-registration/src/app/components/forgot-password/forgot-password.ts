import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { ThemeService } from '../../services/theme.service';

import { DialogService } from '../../services/dialog.service';
import { finalize } from 'rxjs';
@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './forgot-password.html',
  styleUrl: './forgot-password.css',
})
export class ForgotPassword {
  isSaving = false; // disables the submit button while the request runs
  private dialog = inject(DialogService);
  email: string = '';
  errorMessage: string = '';
  successMessage: string = '';

  constructor(
    private http: HttpClient,
    private router: Router,
    public themeService: ThemeService
  ) {}

  toggleDarkMode() {
    this.themeService.toggleDarkMode();
  }

  onSubmit() {
    if (!this.email) {
      this.errorMessage = 'Please enter your email';
      return;
    }

    const formData = new FormData();
    formData.append('email', this.email.trim().toLowerCase());

    this.isSaving = true;
    this.http.post('http://localhost:8000/api/forgot-password', formData)
      .pipe(finalize(() => (this.isSaving = false)))
      .subscribe({
        next: (response: any) => {
          console.log('Password reset link sent', response);
          // Redirect to check email page immediately
          this.dialog.success('Email Sent!', `A password reset link was sent to ${this.email.trim().toLowerCase()}.
If you don't see it in your inbox, check your Spam folder.`);
          this.router.navigate(['/check-email']);
        },
        error: (error) => {
          console.error('Failed to send reset link', error);
          this.dialog.error(
            error.status === 404 ? 'Email Not Registered' : 'Something went wrong',
            error.error?.detail || 'Failed to send reset link. Please try again.'
          );
        }
      });
  }

  goToLogin() {
    this.router.navigate(['/login']);
  }
}
