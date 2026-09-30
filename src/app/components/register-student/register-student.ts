import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { LucideAngularModule, Eye, EyeOff, Check, X } from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';

import { DialogService } from '../../services/dialog.service';
import { finalize } from 'rxjs';
import { PasswordChecklist } from '../password-checklist/password-checklist';
@Component({
  selector: 'app-register-student',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, PasswordChecklist],
  templateUrl: './register-student.html',
  styleUrl: './register-student.css',
})
export class RegisterStudent implements OnInit {
  isSaving = false; // disables the submit button while the request runs
  private dialog = inject(DialogService);
  fullName: string = '';
  role: string = '';
  email: string = '';
  department: string = '';
  password: string = '';
  confirmPassword: string = '';
  errorMessage: string = '';
  successMessage: string = '';

  showPassword: boolean = false;
  showConfirmPassword: boolean = false;
  readonly Eye = Eye;
  readonly EyeOff = EyeOff;
  readonly Check = Check;
  readonly X = X;

  constructor(
    private http: HttpClient,
    private router: Router,
    public themeService: ThemeService
  ) {}

  toggleDarkMode() {
    this.themeService.toggleDarkMode();
  }

  ngOnInit() {
    // Get data from previous page
    this.fullName = sessionStorage.getItem('fullName') || '';
    this.role = sessionStorage.getItem('role') || '';

    // If no data, redirect back to register
    if (!this.fullName || !this.role) {
      this.router.navigate(['/register']);
    }
  }

  onSubmit() {
    this.errorMessage = '';
    this.successMessage = '';

    // Validate passwords match
    if (this.password !== this.confirmPassword) {
      this.errorMessage = 'Passwords do not match';
      return;
    }

    // Validate all fields
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const email = this.email.trim().toLowerCase();
      if (!email || !emailPattern.test(email)) {
        this.errorMessage = 'Please enter a valid email address';
      return;
    }

    if (!this.department || !this.password) {
      this.errorMessage = 'Please fill in all fields';
      return;
    }

    const formData = new FormData();
    formData.append('full_name', this.fullName);
    formData.append('role', this.role);
    formData.append('email', email);
    formData.append('department', this.department);
    formData.append('password', this.password);

    this.isSaving = true;
    this.http.post('http://localhost:8000/api/register/student', formData)
      .pipe(finalize(() => (this.isSaving = false)))
      .subscribe({
        next: (response: any) => {
          this.errorMessage = '';
          sessionStorage.removeItem('fullName');
          sessionStorage.removeItem('role');

          // Account is created only after the emailed 6-digit code is verified
          if (response.email_sent) {
            this.dialog.success('Code Sent!', `We sent a 6-digit verification code to ${response.user.email}. Enter it on the next page to finish creating your account.
If you don't see it in your inbox, check your Spam folder.`);
          } else {
            this.dialog.warning('Email Not Sent',
              'We could not send your verification code. Use "resend code" on the next page to finish creating your account.');
          }
          this.goToVerify(response.user.email);
        },
        error: (error) => {
          console.error('Registration failed', error);
          if (error.error?.verification_required) {
            // Registered before but never verified
            this.dialog.warning('Verify Your Email', error.error.detail);
            this.goToVerify(error.error.email);
            return;
          }
          this.errorMessage = error.error?.detail || 'Registration failed. Please try again.';
          this.successMessage = '';
        }
      });
  }

  goBack() {
    this.router.navigate(['/register']);
  }

  /** Send the user to the Verify Email page for this address. */
  private goToVerify(email: string, resend = false): void {
    this.router.navigate(['/verify-email'], { queryParams: resend ? { email, resend: 1 } : { email } });
  }

  goToLogin(): void {
    this.router.navigate(['/login']);
  }
}
