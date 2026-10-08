import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ThemeService } from '../../services/theme.service';

@Component({
  selector: 'app-check-email',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './check-email.html',
  styleUrl: './check-email.css',
})
export class CheckEmail {
  constructor(
    private router: Router,
    public themeService: ThemeService
  ) {}

  toggleDarkMode() {
    this.themeService.toggleDarkMode();
  }

  backToLogin() {
    this.router.navigate(['/login']);
  }

  tryAnotherEmail() {
    this.router.navigate(['/forgot-password']);
  }
}
