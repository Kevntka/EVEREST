import { ApplicationRef, Component, ViewChild, inject } from '@angular/core';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { bootstrapApplication } from '@angular/platform-browser';
import { changeDetectionInterceptor } from './change-detection.interceptor';

@Component({
  selector: 'test-child',
  template: `<b>{{ items.length }}</b>`,
})
class TestChild {
  items: string[] = [];
  private http = inject(HttpClient);

  load(): void {
    this.http.get<string[]>('/api/child').subscribe((items) => (this.items = items));
  }
}

@Component({
  selector: 'test-root',
  imports: [TestChild],
  template: `<span>{{ items.length }}</span><test-child />`,
})
class TestRoot {
  @ViewChild(TestChild) child!: TestChild;
  items: string[] = [];
  private http = inject(HttpClient);

  load(): void {
    this.http.get<string[]>('/api/items').subscribe((items) => (this.items = items));
  }
}

async function bootstrap(withInterceptor: boolean): Promise<ApplicationRef> {
  document.body.innerHTML = '<test-root></test-root>';
  return bootstrapApplication(TestRoot, {
    providers: [
      provideHttpClient(withInterceptors(withInterceptor ? [changeDetectionInterceptor] : [])),
      provideHttpClientTesting(),
    ],
  });
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 20));

describe('changeDetectionInterceptor (zoneless)', () => {
  it('re-renders the view after an HTTP response', async () => {
    const appRef = await bootstrap(true);
    appRef.components[0].instance.load();
    appRef.injector.get(HttpTestingController).expectOne('/api/items').flush(['a', 'b']);
    await settle();
    expect(document.querySelector('test-root span')?.textContent).toBe('2');
    appRef.destroy();
  });

  it('re-renders a nested (page-like) component after its HTTP response', async () => {
    const appRef = await bootstrap(true);
    await settle();
    appRef.components[0].instance.child.load();
    appRef.injector.get(HttpTestingController).expectOne('/api/child').flush(['a', 'b', 'c']);
    await settle();
    expect(document.querySelector('test-child b')?.textContent).toBe('3');
    appRef.destroy();
  });

  it('does not re-render without the interceptor (control)', async () => {
    const appRef = await bootstrap(false);
    appRef.components[0].instance.load();
    appRef.injector.get(HttpTestingController).expectOne('/api/items').flush(['a', 'b']);
    await settle();
    expect(document.querySelector('test-root span')?.textContent).toBe('0');
    appRef.destroy();
  });
});
