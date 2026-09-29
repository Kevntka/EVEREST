export class RecaptchaService {
  private siteKey = '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI'; // Test key - replace with your actual key
  
  getSiteKey(): string {
    return this.siteKey;
  }
  
  loadScript(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (typeof (window as any).grecaptcha !== 'undefined') {
        resolve();
        return;
      }
      
      const script = document.createElement('script');
      script.src = `https://www.google.com/recaptcha/api.js`;
      script.async = true;
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Failed to load reCAPTCHA'));
      document.head.appendChild(script);
    });
  }
}
