import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Type } from '@angular/core';
import { Organizer } from './organizer/organizer';
import { Students } from './students/students';
import { Participants } from './participants/participants';
import { OrganizerEvents } from './organizer-events/organizer-events';
import { MyEvents } from './my-events/my-events';
import { StudentDashboard } from './student-dashboard/student-dashboard';

/** Three people / events; searching "ana" should leave only the "Ana ..." one. */
const people = [
  { id: 1, full_name: 'ANA SANTOS', email: 'ana@x.com', department: 'CICS', employment_id: 'EMP-1', contact_number: 'N/A' },
  { id: 2, full_name: 'BEN CRUZ', email: 'ben@x.com', department: 'CICS', employment_id: 'EMP-2', contact_number: 'N/A' },
  { id: 3, full_name: 'CARLO REYES', email: 'carlo@x.com', department: 'CICS', employment_id: 'EMP-3', contact_number: 'N/A' },
];
const events = ['Ana Seminar', 'Ben Workshop', 'Carlo Fair'].map((name, i) => ({
  id: i + 1, event_name: name, event_description: '', event_date: '2099-01-01', event_time: '08:00:00',
  event_end_time: '17:00:00', venue: 'Hall', capacity: 10, enrolled_count: 0, status: 'open',
  registration_start: '2000-01-01', registration_end: '2098-12-31', cover_photo: null, attendance: 'present',
}));

const responses: Record<string, unknown> = {
  'http://localhost:8000/api/organizers': { organizers: people },
  'http://localhost:8000/api/students': { students: people },
  'http://localhost:8000/api/participants': { participants: people },
  'http://localhost:8000/api/events': { events },
  'http://localhost:8000/api/student/my-events': { events },
};

/** [page, rows that each show one item, the search input to type in] */
const pages: [string, Type<unknown>, string, string][] = [
  ['admin Organizer', Organizer, 'tbody tr', '.search-input'],
  ['admin Students', Students, 'tbody tr', '.search-input'],
  ['admin Participants', Participants, 'tbody tr', '.search-input'],
  ['organizer Events', OrganizerEvents, '.events-table tbody tr', '.search-input'],
  ['My Events', MyEvents, 'tbody tr', '.search-input'],
  ['Student Dashboard', StudentDashboard, '.event-card', '.search-input'],
];

describe('search bars filter their list', () => {
  for (const [name, component, rowSelector, inputSelector] of pages) {
    it(name, async () => {
      TestBed.configureTestingModule({
        imports: [component],
        providers: [provideRouter([{ path: '**', children: [] }]), provideHttpClient(), provideHttpClientTesting()],
      });
      const http = TestBed.inject(HttpTestingController);
      const fixture = TestBed.createComponent(component);
      const el: HTMLElement = fixture.nativeElement;

      const settle = async () => {
        for (let i = 0; i < 3; i++) {
          await new Promise(r => setTimeout(r));  // Students loads in a setTimeout
          http.match(() => true).forEach(req => req.flush(responses[req.request.urlWithParams.split('?')[0]] ?? {}));
          fixture.detectChanges();
          await fixture.whenStable();
        }
      };
      const rows = () => [...el.querySelectorAll(rowSelector)].map(r => r.textContent || '');

      fixture.detectChanges();
      await settle();
      expect(rows().length).toBe(3);

      const input = el.querySelector(inputSelector) as HTMLInputElement;
      for (const query of ['ana', '  ANA ']) {
        input.value = query;
        input.dispatchEvent(new Event('input'));
        await settle();
        expect(rows().length, `"${query}"`).toBe(1);
        expect(rows()[0].toLowerCase()).toContain('ana');
      }

      input.value = 'zzz';
      input.dispatchEvent(new Event('input'));
      await settle();
      expect(rows().length).toBe(0);

      input.value = '';
      input.dispatchEvent(new Event('input'));
      await settle();
      expect(rows().length).toBe(3);
      fixture.destroy();
    });
  }
});
