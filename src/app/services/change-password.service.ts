import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { DialogService } from './dialog.service';

/**
 * Change Password for a logged-in user: the backend emails a Set New Password
 * link (/reset-password) to the email of the account in the login cookie.
 * Used by the Change Password item in every page's user dropdown.
 */
@Injectable({ providedIn: 'root' })
export class ChangePasswordService {
  private http = inject(HttpClient);
  private dialog = inject(DialogService);
  private sending = false;

  async sendLink(): Promise<void> {
    if (this.sending) return;
    const ok = await this.dialog.confirm('Change Password',
      'We will send a link to your account\'s email. Open it to set your new password.\n\nSend the link now?');
    if (!ok) return;

    this.sending = true;
    try {
      const res = await firstValueFrom(this.http.post<any>(
        'http://localhost:8000/api/change-password', {}, { withCredentials: true }));
      this.dialog.success('Success!',
        `We sent a link to ${res.email}.\nOpen it to set your new password. The link expires in 1 hour.`);
    } catch (error: any) {
      this.dialog.error('Something went wrong', error?.error?.detail || 'Failed to send the link. Please try again.');
    } finally {
      this.sending = false;
    }
  }
}
