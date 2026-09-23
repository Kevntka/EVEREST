import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';

@Component({
  selector: 'app-check-email',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './check-email.html',
  styleUrl: './check-email.css',
})
export class CheckEmail {
  constructor(private router: Router) {}

  backToLogin() {
    this.router.navigate(['/login']);
  }

  tryAnotherEmail() {
    this.router.navigate(['/forgot-password']);
  }
}
