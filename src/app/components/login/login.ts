import { Component, OnInit, AfterViewInit, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router, RouterModule } from '@angular/router';

declare var grecaptcha: any;

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login implements OnInit, AfterViewInit {
  email: string = '';
  password: string = '';
  errorMessage: string = '';
  isSubmitting: boolean = false;
  recaptchaSiteKey: string = '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI'; // Test key
  private recaptchaLoaded: boolean = false;

  constructor(
    private http: HttpClient, 
    private router: Router,
    private ngZone: NgZone
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
    script.src = 'https://www.google.com/recaptcha/api.js';
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
      setTimeout(() => {
        this.ngZone.runOutsideAngular(() => {
          const elements = document.getElementsByClassName('g-recaptcha');
          if (elements.length > 0 && !elements[0].hasChildNodes()) {
            grecaptcha.render(elements[0], {
              'sitekey': this.recaptchaSiteKey
            });
          }
        });
      }, 100);
    }
  }

  onRecaptchaLoad() {
    this.renderRecaptcha();
  }

  getRecaptchaResponse(): string | null {
    if (typeof grecaptcha !== 'undefined') {
      return grecaptcha.getResponse();
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
    formData.append('email', this.email);
    formData.append('password', this.password);
    formData.append('recaptcha_token', recaptchaResponse);

    this.http.post('http://localhost:8000/api/login', formData)
      .subscribe({
        next: (response: any) => {
          console.log('Login successful', response);
          
          // Store user info in localStorage
          localStorage.setItem('userRole', response.role);
          localStorage.setItem('userName', response.name);
          localStorage.setItem('userId', response.id);
          
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
            this.router.navigate(['/dashboard']);
          } else {
            this.router.navigate(['/dashboard']);
          }
        },
        error: (error) => {
          console.error('Login failed', error);
          this.isSubmitting = false;
          
          // Reset reCAPTCHA on error
          if (typeof grecaptcha !== 'undefined') {
            grecaptcha.reset();
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
}
