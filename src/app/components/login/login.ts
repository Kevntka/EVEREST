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
  recaptchaSiteKey: string = '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI'; // Test key
  private recaptchaLoaded: boolean = false;
  private recaptchaWidgetId: number | null = null;

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
    if (this.recaptchaLoaded && typeof grecaptcha !== 'undefined') {
      // ready() waits until render() is usable (onload can fire before that)
      grecaptcha.ready(() => {
        this.ngZone.runOutsideAngular(() => {
          const elements = document.getElementsByClassName('g-recaptcha');
          if (elements.length > 0) {
            // Remove existing widget if it exists
            if (this.recaptchaWidgetId !== null) {
              try {
                elements[0].innerHTML = '';
                this.recaptchaWidgetId = null;
              } catch (e) {
                console.log('Error clearing recaptcha:', e);
              }
            }
            
            // Render new widget with current theme
            try {
              this.recaptchaWidgetId = grecaptcha.render(elements[0], {
                'sitekey': this.recaptchaSiteKey,
                'theme': this.themeService.isDarkMode() ? 'dark' : 'light'
              });
            } catch (e) {
              console.log('Error rendering recaptcha:', e);
            }
          }
        });
      });
    }
  }

  getRecaptchaResponse(): string | null {
    if (typeof grecaptcha !== 'undefined') {
      // Try with widget ID first
      if (this.recaptchaWidgetId !== null) {
        const response = grecaptcha.getResponse(this.recaptchaWidgetId);
        if (response) return response;
      }
      // Fallback: try without widget ID (works if only one reCAPTCHA on page)
      try {
        const response = grecaptcha.getResponse();
        if (response) return response;
      } catch (e) {
        console.log('Error getting recaptcha response:', e);
      }
    }
    return null;
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
          if (typeof grecaptcha !== 'undefined' && this.recaptchaWidgetId !== null) {
            grecaptcha.reset(this.recaptchaWidgetId);
          }
          
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
    // Re-render reCAPTCHA with new theme
    this.renderRecaptcha();
  }
}
