import { Component, OnInit, AfterViewInit, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router, RouterModule } from '@angular/router';
import { LucideAngularModule, Eye, EyeOff } from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';

declare var grecaptcha: any;

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, LucideAngularModule],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login implements OnInit, AfterViewInit {
  email: string = '';
  password: string = '';
  errorMessage: string = '';
  isSubmitting: boolean = false;
  showPassword: boolean = false;
  readonly Eye = Eye;
  readonly EyeOff = EyeOff;
  recaptchaSiteKey: string = '6LeU3eQtAAAAACCzIedMrlwPCVsFaMnzfcQvdseG'; // reCAPTCHA v2 Checkbox (public key; the secret is RECAPTCHA_SECRET_KEY in backend/.env)
  private recaptchaLoaded: boolean = false;
  /**
   * One widget per theme, each rendered once. Google can't restyle a widget, and
   * clearing + re-rendering on every theme toggle broke when toggled quickly (the
   * widget disappeared), so the toggle only switches which one is visible.
   */
  private recaptchaWidgets: { light: number | null; dark: number | null } = { light: null, dark: null };
  private recaptchaRendered = false;

  constructor(
    private http: HttpClient, 
    private router: Router,
    private ngZone: NgZone,
    public themeService: ThemeService
  ) {}

  ngOnInit() {
    // Load reCAPTCHA script
    this.loadRecaptchaScript();
  }

  ngAfterViewInit() {
    // Render reCAPTCHA after view is initialized
    this.renderRecaptcha();
  }

  loadRecaptchaScript() {
    if (typeof grecaptcha !== 'undefined') {
      this.recaptchaLoaded = true;
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://www.google.com/recaptcha/api.js?render=explicit';
    script.async = true;
    script.defer = true;
    script.onload = () => {
      this.recaptchaLoaded = true;
      this.renderRecaptcha();
    };
    document.head.appendChild(script);
  }

  renderRecaptcha() {
    if (!this.recaptchaLoaded || typeof grecaptcha === 'undefined' || this.recaptchaRendered) return;
    // ready() waits until render() is usable (onload can fire before that)
    grecaptcha.ready(() => {
      this.ngZone.runOutsideAngular(() => {
        const container = document.getElementsByClassName('g-recaptcha')[0];
        if (!container || this.recaptchaRendered) return;
        this.recaptchaRendered = true;
        container.innerHTML = '';
        for (const theme of ['light', 'dark'] as const) {
          const target = document.createElement('div');
          target.dataset['theme'] = theme;
          container.appendChild(target);
          try {
            this.recaptchaWidgets[theme] = grecaptcha.render(target, { sitekey: this.recaptchaSiteKey, theme });
          } catch (e) {
            console.log('Error rendering recaptcha:', e);
          }
        }
        this.showRecaptchaForTheme();
      });
    });
  }

  /** Show the widget that matches the current theme; hide the other. */
  private showRecaptchaForTheme(): void {
    const visible = this.themeService.isDarkMode() ? 'dark' : 'light';
    document.querySelectorAll<HTMLElement>('.g-recaptcha > [data-theme]').forEach(el => {
      el.style.display = el.dataset['theme'] === visible ? '' : 'none';
    });
  }

  /** Widget id of the reCAPTCHA the user can currently see. */
  private get visibleWidgetId(): number | null {
    return this.recaptchaWidgets[this.themeService.isDarkMode() ? 'dark' : 'light'];
  }

  getRecaptchaResponse(): string | null {
    const id = this.visibleWidgetId;
    if (typeof grecaptcha === 'undefined' || id === null) return null;
    try {
      return grecaptcha.getResponse(id) || null;
    } catch (e) {
      console.log('Error getting recaptcha response:', e);
      return null;
    }
  }

  /** Clear both checkboxes after a failed login. */
  private resetRecaptcha(): void {
    if (typeof grecaptcha === 'undefined') return;
    for (const id of [this.recaptchaWidgets.light, this.recaptchaWidgets.dark]) {
      if (id !== null) {
        try { grecaptcha.reset(id); } catch { /* not ready yet */ }
      }
    }
  }

  onSubmit() {
    // Get reCAPTCHA response
    const recaptchaResponse = this.getRecaptchaResponse();
    
    if (!recaptchaResponse) {
      this.errorMessage = 'Please complete the reCAPTCHA verification';
      return;
    }

    this.isSubmitting = true;
    this.errorMessage = '';

    const formData = new FormData();
    formData.append('email', this.email.trim().toLowerCase());
    formData.append('password', this.password);
    formData.append('recaptcha_token', recaptchaResponse);

    this.http.post('http://localhost:8000/api/login', formData, { withCredentials: true })
      .subscribe({
        next: (response: any) => {
          console.log('Login successful', response);
          
          // Store user info in localStorage
          localStorage.setItem('userRole', response.role);
          localStorage.setItem('userName', response.name);
          localStorage.setItem('userId', response.id);
          localStorage.setItem('userEmail', this.email.trim().toLowerCase());
          
          // For organizer, store additional info
          if (response.role === 'organizer') {
            localStorage.setItem('organizerName', response.name);
            localStorage.setItem('organizerId', response.id);
          }
          
          // Redirect based on role
          if (response.role === 'admin') {
            this.router.navigate(['/dashboard']);
          } else if (response.role === 'organizer') {
            this.router.navigate(['/organizer-dashboard']);
          } else if (response.role === 'student') {
            this.router.navigate(['/student-dashboard']);
          } else if (response.role === 'participant') {
            this.router.navigate(['/student-dashboard']);
          } else {
            this.router.navigate(['/dashboard']);
          }
        },
        error: (error) => {
          console.error('Login failed', error);
          this.isSubmitting = false;
          
          // Reset reCAPTCHA on error
          this.resetRecaptcha();
          
          // Unverified student/participant: go verify (a fresh link is sent there)
          if (error.status === 403 && error.error?.verification_required) {
            this.errorMessage = '';
            this.router.navigate(['/verify-email'], { queryParams: { email: error.error.email, resend: 1 } });
            return;
          }

          // Show error message
          if (error.error && error.error.detail) {
            this.errorMessage = error.error.detail;
          } else {
            this.errorMessage = 'Login failed. Please try again.';
          }
        },
        complete: () => {
          this.isSubmitting = false;
        }
      });
  }

  toggleDarkMode() {
    this.themeService.toggleDarkMode();
    // Swap to the widget in the new theme (no re-render, so fast toggling can't lose it)
    this.showRecaptchaForTheme();
  }
}
