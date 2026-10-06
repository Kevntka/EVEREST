import { Component, inject } from '@angular/core';
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
  selector: 'app-register-organizer',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, PasswordChecklist],
  templateUrl: './register-organizer.html',
  styleUrl: '../register-student/register-student.css', // same look as the student form
})
/**
 * Organizer self-registration, opened from "Are you an organizer?" on the login page.
 * Same flow as students: the account is created once the emailed Verify Account link is opened.
 */
export class RegisterOrganizer {
  isSaving = false; // disables the submit button while the request runs
  private dialog = inject(DialogService);
  fullName: string = '';
  employmentId: string = '';
  email: string = '';
  department: string = '';
  contactNumber: string = '';
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

    if (!this.fullName.trim() || !this.employmentId.trim() || !this.department.trim() || !this.password) {
      this.errorMessage = 'Please fill in all required fields';
      return;
    }

    const formData = new FormData();
    formData.append('full_name', this.fullName.trim());
    formData.append('employment_id', this.employmentId.trim());
    formData.append('email', email);
    formData.append('department', this.department.trim());
    formData.append('password', this.password);
    if (this.contactNumber.trim()) {
      formData.append('contact_number', this.contactNumber.trim());
    }

    this.isSaving = true;
    this.http.post('http://localhost:8000/api/register/organizer', formData)
      .pipe(finalize(() => (this.isSaving = false)))
      .subscribe({
        next: (response: any) => {
          this.errorMessage = '';

          // Account is created only after the emailed Verify Account link is opened
          if (response.email_sent) {
            this.dialog.success('Check Your Email', `We sent a verification link to ${response.user.email}. Click Verify Account in the email to finish creating your account.
If you don't see it in your inbox, check your Spam folder.`);
          } else {
            this.dialog.warning('Email Not Sent',
              'We could not send your verification link. Use "resend link" on the next page to finish creating your account.');
          }
          this.goToVerify(response.user.email);
        },
        error: (error) => {
          console.error('Registration failed', error);
          if (error.error?.verification_required) {
            // Registered before but never verified
            this.dialog.warning('Verify Your Account', error.error.detail);
            this.goToVerify(error.error.email);
            return;
          }
          this.errorMessage = error.error?.detail || 'Registration failed. Please try again.';
          this.successMessage = '';
        }
      });
  }

  /** Send the user to the Verify Email page for this address. */
  private goToVerify(email: string, resend = false): void {
    this.router.navigate(['/verify-email'], { queryParams: resend ? { email, resend: 1 } : { email } });
  }

  goToLogin(): void {
    this.router.navigate(['/login']);
  }
}
