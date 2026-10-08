import { Directive, ElementRef, HostListener, inject, output } from '@angular/core';

/**
 * Emits when the user clicks anywhere outside the host element.
 * Used to close the top-bar user dropdown: <div class="user-menu" (clickOutside)="showDropdown = false">
 */
@Directive({
  selector: '[clickOutside]',
  standalone: true
})
export class ClickOutsideDirective {
  readonly clickOutside = output<void>();

  private readonly host = inject(ElementRef<HTMLElement>);

  @HostListener('document:click', ['$event.target'])
  onDocumentClick(target: EventTarget | null): void {
    if (target instanceof Node && !this.host.nativeElement.contains(target)) {
      this.clickOutside.emit();
    }
  }
}
