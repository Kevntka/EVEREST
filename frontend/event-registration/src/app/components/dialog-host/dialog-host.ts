import { Component, HostListener, inject } from '@angular/core';
import { LucideAngularModule, Check, X } from 'lucide-angular';
import { DialogService } from '../../services/dialog.service';

@Component({
  selector: 'app-dialog-host',
  standalone: true,
  imports: [LucideAngularModule],
  templateUrl: './dialog-host.html',
  styleUrl: './dialog-host.css'
})
export class DialogHost {
  readonly dialog = inject(DialogService);

  readonly Check = Check;
  readonly X = X;

  /** Any click closes a notice; the confirm dialog needs Cancel or OK. */
  onOverlayClick(): void {
    const state = this.dialog.state();
    if (state && state.kind !== 'confirm') {
      this.dialog.close();
    }
  }

  /** Escape closes a notice or cancels a confirm. */
  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.dialog.state()) {
      this.dialog.close(false);
    }
  }
}
