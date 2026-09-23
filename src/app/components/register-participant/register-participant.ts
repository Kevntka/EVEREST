import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';

@Component({
  selector: 'app-register-participant',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './register-participant.html',
  styleUrl: './register-participant.css',
})
export class RegisterParticipant implements OnInit {
  fullName: string = '';
  role: string = '';
  email: string = '';
  contactNumber: string = '';
  password: string = '';
  confirmPassword: string = '';
  errorMessage: string = '';
  successMessage: string = '';

  constructor(private http: HttpClient, private router: Router) {}

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

    this.http.post('http://localhost:8000/api/register/participant', formData)
      .subscribe({
        next: (response: any) => {
          console.log('Registration successful', response);
          this.successMessage = 'Registration successful! Redirecting to login...';
          this.errorMessage = '';
          
          // Clear session storage
          sessionStorage.removeItem('fullName');
          sessionStorage.removeItem('role');
          
          // Redirect to login after 2 seconds
          setTimeout(() => {
            this.router.navigate(['/login']);
          }, 2000);
        },
        error: (error) => {
          console.error('Registration failed', error);
          this.errorMessage = 'Registration failed. Please try again.';
          this.successMessage = '';
        }
      });
  }

  goBack() {
    this.router.navigate(['/register']);
  }
}
