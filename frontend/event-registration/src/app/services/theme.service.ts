import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class ThemeService {
  private darkMode = false;

  constructor() {
    // Load saved theme preference from localStorage
    const savedTheme = localStorage.getItem('darkMode');
    this.darkMode = savedTheme === 'true';
    this.applyTheme();
  }

  /**
   * Toggle dark mode on/off
   */
  toggleDarkMode(): void {
    this.darkMode = !this.darkMode;
    localStorage.setItem('darkMode', this.darkMode.toString());
    this.applyTheme();
    this.toggleCount++;
    this.lastToggleAt = Date.now();
  }

  /**
   * Check if dark mode is enabled
   */
  isDarkMode(): boolean {
    return this.darkMode;
  }

  /**
   * Sidebar logo for the current theme (the SVG's "EVENTS" text color is
   * baked into the file, so dark mode needs its own version)
   */
  logoSrc(): string {
    return this.darkMode ? '/assets/images/events-logo-dark.svg' : '/assets/images/events-logo.svg';
  }

  private toggleCount = 0;
  private lastToggleAt = 0;

  /**
   * CSS class that spins the Sun/Moon icon right after a toggle.
   * Alternates between two classes so rapid toggles restart the animation,
   * and returns '' later so re-opening a dropdown doesn't spin the icon.
   */
  themeIconSpinClass(): string {
    if (Date.now() - this.lastToggleAt > 600) return '';
    return this.toggleCount % 2 ? 'theme-icon-spin-a' : 'theme-icon-spin-b';
  }

  /**
   * Apply theme to document
   */
  private applyTheme(): void {
    if (this.darkMode) {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }
  }
}
