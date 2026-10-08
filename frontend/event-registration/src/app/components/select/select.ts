import { Component, ElementRef, HostBinding, HostListener, Input, forwardRef, inject, signal } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

export interface SelectOption {
  value: string;
  label: string;
}

/**
 * Dropdown used instead of the native <select>, whose option list is drawn by the
 * browser/OS and can't be styled (in phone emulation it pops up huge, outside the page).
 * Works with [(ngModel)]. The host element is the box, so the page's existing select
 * class keeps styling it (border, padding, arrow, :focus, dark mode):
 *
 *   <app-select class="department-select" [options]="departmentOptions" [(ngModel)]="selectedDepartment"></app-select>
 *
 * `placeholder` is shown while the value matches no option (e.g. "Role" before choosing).
 */
@Component({
  selector: 'app-select',
  standalone: true,
  providers: [{ provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => SelectComponent), multi: true }],
  template: `
    <span class="value" [class.placeholder]="!selected()">{{ selected()?.label ?? placeholder }}</span>
    <svg class="chevron" [class.up]="open()" viewBox="0 0 12 12" aria-hidden="true"><path d="M6 9L1 4h10z" /></svg>
    @if (open()) {
      <ul class="panel" [class.above]="openAbove()" role="listbox" (click)="$event.stopPropagation()">
        @for (option of options; track option.value; let i = $index) {
          <li role="option"
              [attr.aria-selected]="option.value === value()"
              [class.selected]="option.value === value()"
              [class.active]="i === activeIndex()"
              [attr.title]="option.label"
              (mouseenter)="activeIndex.set(i)"
              (click)="choose(option)">{{ option.label }}</li>
        }
      </ul>
    }
  `,
  styles: [`
    /* The arrow is drawn here (.chevron) for every dropdown, so any arrow image a
       page's old select class sets is turned off to avoid showing two */
    :host {
      display: inline-block;
      position: relative;
      background-image: none !important;
      cursor: pointer;
      user-select: none;
      text-align: left;
      outline: none;
    }

    .value {
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .value {
      padding-right: 22px;
    }

    .chevron {
      position: absolute;
      right: 12px;
      top: 50%;
      width: 12px;
      height: 12px;
      margin-top: -6px;
      fill: #6c757d;
      transition: transform 0.2s ease;
      pointer-events: none;
    }

    .chevron.up {
      transform: rotate(180deg);
    }

    :host-context(body.dark-mode) .chevron {
      fill: #b0b0b0;
    }

    .value.placeholder {
      opacity: 0.6;
    }

    .panel {
      position: absolute;
      top: calc(100% + 4px);
      left: -1px;
      /* at least as wide as the box; wider for long options (e.g. department names) */
      min-width: calc(100% + 2px);
      width: max-content;
      max-width: min(320px, 90vw);
      z-index: 1000;
      margin: 0;
      padding: 4px 0;
      list-style: none;
      max-height: 240px;
      overflow-y: auto;
      background-color: #ffffff;
      border: 1px solid #dee2e6;
      border-radius: 6px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
      font-size: 14px;
      color: #212529;
    }

    /* Long lists still scroll (wheel, touch, arrow keys) but without a scrollbar, like the short lists */
    .panel {
      scrollbar-width: none;
    }

    .panel::-webkit-scrollbar {
      display: none;
    }

    .panel.above {
      top: auto;
      bottom: calc(100% + 4px);
    }

    li {
      padding: 8px 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    li.active {
      background-color: #f1f3f5;
    }

    li.selected {
      color: #dc3545;
      font-weight: 600;
    }

    :host-context(body.dark-mode) .panel {
      background-color: #2d2d2d;
      border-color: #404040;
      color: #ffffff;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    }

    :host-context(body.dark-mode) li.active {
      background-color: #3a3a3a;
    }

    :host-context(body.dark-mode) li.selected {
      color: #ff6b6b;
    }
  `]
})
export class SelectComponent implements ControlValueAccessor {
  @Input() options: SelectOption[] = [];
  @Input() placeholder = '';

  @HostBinding('attr.tabindex') readonly tabindex = 0;
  @HostBinding('attr.role') readonly role = 'combobox';
  @HostBinding('attr.aria-expanded') get expanded() { return this.open(); }

  readonly value = signal('');
  readonly open = signal(false);
  readonly openAbove = signal(false);
  readonly activeIndex = signal(-1);

  private readonly host = inject(ElementRef<HTMLElement>);
  private onChange: (value: string) => void = () => {};
  private onTouched: () => void = () => {};

  selected(): SelectOption | undefined {
    return this.options.find(o => o.value === this.value());
  }

  @HostListener('click')
  toggle(): void {
    this.open() ? this.close() : this.show();
  }

  @HostListener('keydown', ['$event'])
  onKeydown(event: KeyboardEvent): void {
    const last = this.options.length - 1;
    switch (event.key) {
      case 'Enter':
      case ' ':
        event.preventDefault();
        if (this.open() && this.options[this.activeIndex()]) this.choose(this.options[this.activeIndex()]);
        else this.toggle();
        break;
      case 'ArrowDown':
        event.preventDefault();
        if (!this.open()) this.show();
        else this.activeIndex.set(Math.min(last, this.activeIndex() + 1));
        this.revealActive();
        break;
      case 'ArrowUp':
        event.preventDefault();
        if (!this.open()) this.show();
        else this.activeIndex.set(Math.max(0, this.activeIndex() - 1));
        this.revealActive();
        break;
      case 'Escape':
      case 'Tab':
        this.close();
        break;
    }
  }

  /** The list has no scrollbar, so keep the highlighted option in view (after the view updates). */
  private revealActive(): void {
    requestAnimationFrame(() => {
      const items = this.host.nativeElement.querySelectorAll('li');
      items[this.activeIndex()]?.scrollIntoView({ block: 'nearest' });
    });
  }

  @HostListener('document:click', ['$event.target'])
  onDocumentClick(target: EventTarget | null): void {
    if (this.open() && target instanceof Node && !this.host.nativeElement.contains(target)) this.close();
  }

  @HostListener('blur')
  onBlur(): void {
    this.onTouched();
  }

  choose(option: SelectOption): void {
    this.close();
    if (option.value === this.value()) return;
    this.value.set(option.value);
    this.onChange(option.value);
  }

  private show(): void {
    // Open upward when there isn't room for the list below the box
    const box = this.host.nativeElement.getBoundingClientRect();
    this.openAbove.set(window.innerHeight - box.bottom < 260 && box.top > window.innerHeight - box.bottom);
    this.activeIndex.set(Math.max(0, this.options.findIndex(o => o.value === this.value())));
    this.open.set(true);
    this.revealActive(); // a chosen option far down the list is shown, not hidden below
  }

  private close(): void {
    this.open.set(false);
  }

  writeValue(value: string | null): void {
    this.value.set(value ?? '');
  }

  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }
}
