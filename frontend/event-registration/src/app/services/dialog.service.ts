import { Injectable, signal } from '@angular/core';

export type DialogKind = 'confirm' | 'success' | 'warning' | 'error';

export interface DialogState {
  kind: DialogKind;
  title: string;
  message: string;
  confirmText?: string;
}

/**
 * In-app replacement for window.confirm/alert, rendered once by
 * <app-dialog-host> in app.html. State is a signal, so it re-renders
 * on its own in this zoneless app.
 *
 * confirm() is the only dialog with buttons (Cancel / OK). Notices
 * (success, warning, error) have no buttons and close on any click.
 */
@Injectable({
  providedIn: 'root'
})
export class DialogService {
  readonly state = signal<DialogState | null>(null);

  private resolveConfirm: ((ok: boolean) => void) | null = null;

  /** "Warning" dialog with Cancel / OK; resolves true on OK, false on Cancel. */
  confirm(title: string, message: string, confirmText = 'OK'): Promise<boolean> {
    this.close(false);
    this.state.set({ kind: 'confirm', title, message, confirmText });
    return new Promise(resolve => (this.resolveConfirm = resolve));
  }

  success(title: string, message: string): void {
    this.show({ kind: 'success', title, message });
  }

  /** Partial success the user should read (e.g. created but email failed). */
  warning(title: string, message: string): void {
    this.show({ kind: 'warning', title, message });
  }

  error(title: string, message: string): void {
    this.show({ kind: 'error', title, message });
  }

  close(result = false): void {
    this.resolveConfirm?.(result);
    this.resolveConfirm = null;
    this.state.set(null);
  }

  private show(state: DialogState): void {
    this.close(false);
    this.state.set(state);
  }
}
