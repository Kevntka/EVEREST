import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './forgot-password.html',
  styleUrl: './forgot-password.css',
})
export class ForgotPassword {
  email: string = '';
  errorMessage: string = '';
  successMessage: string = '';

  constructor(private http: HttpClient, private router: Router) {}

  onSubmit() {
    if (!this.email) {
      this.errorMessage = 'Please enter your email';
      return;
    }

    const formData = new FormData();
    formData.append('email', this.email);

    this.http.post('http://localhost:8000/api/forgot-password', formData)
      .subscribe({
        next: (response: any) => {
          console.log('Password reset link sent', response);
          // Redirect to check email page immediately
          this.router.navigate(['/check-email']);
        },
        error: (error) => {
          console.error('Failed to send reset link', error);
          this.errorMessage = 'Failed to send reset link. Please try again.';
          this.successMessage = '';
        }
      });
  }

  goToLogin() {
    this.router.navigate(['/login']);
  }
}
