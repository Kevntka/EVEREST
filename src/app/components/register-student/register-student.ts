import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';

@Component({
  selector: 'app-register-student',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './register-student.html',
  styleUrl: './register-student.css',
})
export class RegisterStudent implements OnInit {
  fullName: string = '';
  role: string = '';
  gsuite: string = '';
  department: string = '';
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
    if (!this.gsuite || !this.department || !this.password) {
      this.errorMessage = 'Please fill in all fields';
      return;
    }

    const formData = new FormData();
    formData.append('full_name', this.fullName);
    formData.append('role', this.role);
    formData.append('gsuite', this.gsuite);
    formData.append('department', this.department);
    formData.append('password', this.password);

    this.http.post('http://localhost:8000/api/register/student', formData)
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
