import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './register.html',
  styleUrl: './register.css',
})
export class Register {
  fullName: string = '';
  role: string = '';
  errorMessage: string = '';

  roles: string[] = ['Student', 'Participant'];

  constructor(private router: Router) {}

  onSubmit() {
    if (!this.fullName || !this.role) {
      this.errorMessage = 'Please fill in all fields';
      return;
    }

    // Store the data in sessionStorage to pass to next page
    sessionStorage.setItem('fullName', this.fullName);
    sessionStorage.setItem('role', this.role);

    // Navigate to appropriate registration page based on role
    if (this.role === 'Student') {
      this.router.navigate(['/register/student']);
    } else if (this.role === 'Participant') {
      this.router.navigate(['/register/participant']);
    } else {
      // For other roles, show message for now
      this.errorMessage = 'Only Student and Participant registration is available for now';
    }
  }

  goToLogin() {
    this.router.navigate(['/login']);
  }
}
