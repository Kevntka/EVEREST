import { ApplicationRef, Component } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { ClickOutsideDirective } from './click-outside.directive';

@Component({
  selector: 'test-menu-host',
  imports: [ClickOutsideDirective],
  template: `
    <div class="user-menu" (clickOutside)="showDropdown = false">
      <button class="toggle" (click)="showDropdown = !showDropdown">menu</button>
      @if (showDropdown) { <div class="dropdown-menu"><button class="item">Dark Mode</button></div> }
    </div>
    <p class="elsewhere">page content</p>
  `
})
class TestMenuHost {
  showDropdown = false;
}

const settle = () => new Promise(resolve => setTimeout(resolve, 20));
const click = (selector: string) =>
  (document.querySelector(selector) as HTMLElement).dispatchEvent(new MouseEvent('click', { bubbles: true }));

describe('ClickOutsideDirective (zoneless)', () => {
  let appRef: ApplicationRef;

  beforeEach(async () => {
    document.body.innerHTML = '<test-menu-host></test-menu-host>';
    appRef = await bootstrapApplication(TestMenuHost);
  });

  afterEach(() => appRef.destroy());

  it('closes the dropdown when clicking elsewhere on the page', async () => {
    click('.toggle');
    await settle();
    expect(document.querySelector('.dropdown-menu')).not.toBeNull();

    click('.elsewhere');
    await settle();
    expect(document.querySelector('.dropdown-menu')).toBeNull();
  });

  it('keeps the dropdown open when clicking inside the menu', async () => {
    click('.toggle');
    await settle();
    click('.item');
    await settle();
    expect(document.querySelector('.dropdown-menu')).not.toBeNull();
  });
});
