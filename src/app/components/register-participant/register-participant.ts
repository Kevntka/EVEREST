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
  selector: 'app-register-participant',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, PasswordChecklist],
  templateUrl: './register-participant.html',
  styleUrl: './register-participant.css',
})
export class RegisterParticipant implements OnInit {
  isSaving = false; // disables the submit button while the request runs
  private dialog = inject(DialogService);
  fullName: string = '';
  role: string = '';
  email: string = '';
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

  ngOnInit() {
    // Get data from previous page
    this.fullName = sessionStorage.getItem('fullName') || '';
    this.role = sessionStorage.getItem('role') || '';

    // If no data, redirect back to register
    if (!this.fullName || !this.role) {
      this.router.navigate(['/register']);
    }
  }

  /** Digits only, formatted as 0912-345-6789 as the user types. */
  onContactInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const digits = input.value.replace(/\D/g, '').slice(0, 11);
    const value = digits.length <= 4 ? digits
      : digits.length <= 7 ? `${digits.slice(0, 4)}-${digits.slice(4)}`
      : `${digits.slice(0, 4)}-${digits.slice(4, 7)}-${digits.slice(7)}`;
    if (input.value !== value) input.value = value;
    this.contactNumber = value;
  }

  onSubmit() {
    // Validate passwords match
    if (this.password !== this.confirmPassword) {
      this.errorMessage = 'Passwords do not match';
      return;
    }

    // Validate all fields
    if (!this.email || !this.contactNumber || !this.password) {
      this.errorMessage = 'Please fill in all fields';
      return;
    }

    const formData = new FormData();
    formData.append('full_name', this.fullName);
    formData.append('role', this.role);
    formData.append('email', this.email);
    formData.append('contact_number', this.contactNumber);
    formData.append('password', this.password);

    this.isSaving = true;
    this.http.post('http://localhost:8000/api/register/participant', formData)
      .pipe(finalize(() => (this.isSaving = false)))
      .subscribe({
        next: (response: any) => {
          this.errorMessage = '';
          sessionStorage.removeItem('fullName');
          sessionStorage.removeItem('role');

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
