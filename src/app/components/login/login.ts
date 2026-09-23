import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router, RouterModule } from '@angular/router';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {
  email: string = '';
  password: string = '';
  captchaChecked: boolean = false;
  errorMessage: string = '';

  constructor(private http: HttpClient, private router: Router) {}

  onSubmit() {
    if (!this.captchaChecked) {
      this.errorMessage = 'Please check the captcha';
      return;
    }

    const formData = new FormData();
    formData.append('email', this.email);
    formData.append('password', this.password);
    formData.append('captcha', this.captchaChecked.toString());

    this.http.post('http://localhost:8000/api/login', formData)
      .subscribe({
        next: (response) => {
          console.log('Login successful', response);
          // Handle successful login (e.g., navigate to dashboard)
        },
        error: (error) => {
          console.error('Login failed', error);
          this.errorMessage = 'Invalid email or password';
        }
      });
  }
}
