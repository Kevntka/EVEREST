import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { LucideAngularModule, Eye, EyeOff } from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';
import { HttpClient } from '@angular/common/http';

import { DialogService } from '../../services/dialog.service';
import { PasswordChecklist } from '../password-checklist/password-checklist';
@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, PasswordChecklist],
  templateUrl: './reset-password.html',
  styleUrl: './reset-password.css'
})
export class ResetPassword implements OnInit {
  private dialog = inject(DialogService);
  token: string = '';
  newPassword: string = '';
  confirmPassword: string = '';
  isLoading: boolean = false;

  showPassword: boolean = false;
  showConfirmPassword: boolean = false;
  readonly Eye = Eye;
  readonly EyeOff = EyeOff;

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private http: HttpClient,
    public themeService: ThemeService
  ) {}

  toggleDarkMode() {
    this.themeService.toggleDarkMode();
  }

  ngOnInit(): void {
    // Get token from URL query parameter
    this.route.queryParams.subscribe(params => {
      this.token = params['token'] || '';
      if (!this.token) {
        this.dialog.error('Invalid Link', 'Invalid reset link');
        this.router.navigate(['/login']);
      }
    });
  }

  resetPassword(): void {
    // Validation
    if (!this.newPassword || !this.confirmPassword) {
      this.dialog.error('Check your input', 'Please fill in all fields');
      return;
    }

    if (this.newPassword !== this.confirmPassword) {
      this.dialog.error('Check your input', 'Passwords do not match');
      return;
    }

    this.isLoading = true;

    const formData = new FormData();
    formData.append('token', this.token);
    formData.append('new_password', this.newPassword);

    this.http.post<any>('http://localhost:8000/api/reset-password', formData)
      .subscribe({
        next: (response) => {
          this.dialog.success('Success!', 'Password reset successfully! You can now login.');
          this.router.navigate(['/login']);
        },
        error: (error) => {
          this.isLoading = false;
          let errorMessage = 'Failed to reset password';
          
          if (error.error?.detail) {
            errorMessage = error.error.detail;
          }
          
          this.dialog.error('Something went wrong', errorMessage);
        }
      });
  }

  backToLogin(): void {
    this.router.navigate(['/login']);
  }
}
