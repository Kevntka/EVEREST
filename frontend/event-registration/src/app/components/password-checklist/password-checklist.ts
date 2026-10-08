import { Component, Input } from '@angular/core';
import { PASSWORD_RULES } from '../../utils/password-policy';

const STRENGTH = [
  { label: 'Weak', color: '#dc3545' },   // 0-2 rules met
  { label: 'Weak', color: '#dc3545' },
  { label: 'Weak', color: '#dc3545' },
  { label: 'Fair', color: '#f59e0b' },   // 3
  { label: 'Good', color: '#84cc16' },   // 4
  { label: 'Strong', color: '#16a34a' }, // 5 (all rules met)
];

/**
 * Password strength bar shown under the confirm-password field. It only rates the
 * password (Weak / Fair / Good / Strong); any non-empty password is accepted.
 */
@Component({
  selector: 'app-password-checklist',
  standalone: true,
  template: `
    <div class="password-strength" [attr.aria-label]="'Password strength: ' + strength.label" aria-live="polite">
      <div class="meter" role="presentation">
        @for (segment of segments; track $index) {
          <span class="segment" [style.background-color]="$index < metCount ? strength.color : null"></span>
        }
      </div>
      <span class="strength-label" [style.color]="strength.color">{{ password ? strength.label : '' }}</span>
    </div>
    <p class="password-note">
      Note: Use 8+ characters with uppercase, lowercase, number &amp; symbol.
    </p>
  `,
  styles: [`
    :host {
      display: block;
      margin-top: 10px;
    }
    .password-strength {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .meter {
      flex: 1;
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 4px;
    }
    .segment {
      height: 4px;
      border-radius: 2px;
      background-color: #e5e7eb;
      transition: background-color 0.2s ease;
    }
    .strength-label {
      min-width: 48px;
      font-size: 12px;
      font-weight: 600;
      text-align: right;
    }
    .password-note {
      margin: 8px 0 0;
      font-size: 12px;
      line-height: 1.45;
      color: #6b7280;
      text-align: left;
    }
    :host-context(body.dark-mode) .segment {
      background-color: #4b5563;
    }
    :host-context(body.dark-mode) .password-note {
      color: #9ca3af;
    }
  `]
})
export class PasswordChecklist {
  @Input() password = '';

  readonly segments = PASSWORD_RULES;

  get metCount(): number {
    return PASSWORD_RULES.filter(rule => rule.test(this.password || '')).length;
  }

  get strength() {
    return STRENGTH[this.metCount];
  }
}
