import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import {
  LucideAngularModule,
  LayoutDashboard,
  UserCircle,
  Calendar,
  Menu,
  User,
  ChevronDown,
  Search,
  Moon, Sun,
  LogOut,
  Key
} from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';
import { formatTimeRange } from '../../utils/event-time';
import { DialogService } from '../../services/dialog.service';
import { DisplayCasePipe } from '../../utils/display-case.pipe';
import { autoRefresh } from '../../utils/auto-refresh';
import { ChangePasswordService } from '../../services/change-password.service';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';

export interface MyEvent {
  id: number;
  title: string;
  date: string | null;
  time: string; // '8:00 AM - 5:00 PM'
  venue: string;
  attendance: 'present' | 'not_recorded' | 'pending';  // set by the organizer; pending = not marked yet
}

const PAGE_SIZE = 10;

/**
 * "My Events" for students and participants: the events they enrolled in, with
 * their attendance. Shares the Student Dashboard's sidebar, top bar and styles.
 */
@Component({
  selector: 'app-my-events',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective, DisplayCasePipe],
  templateUrl: './my-events.html',
  styleUrls: ['../student-dashboard/student-dashboard.css', './my-events.css']
})
export class MyEvents implements OnInit {
  private dialog = inject(DialogService);
  /** Re-fetch every 10s so statuses (Open / Full / Closed / Upcoming) update without a reload. */
  private autoRefresh = autoRefresh(() => this.loadMyEvents(true));
  private changePasswordService = inject(ChangePasswordService);
  private router = inject(Router);
  private http = inject(HttpClient);
  readonly themeService = inject(ThemeService);

  showDropdown = false;
  sidebarOpen = true;
  studentName = 'Student';
  readonly roleLabel = localStorage.getItem('userRole') === 'participant' ? 'Participant' : 'Student';
  readonly isStudent = localStorage.getItem('userRole') !== 'participant';

  events: MyEvent[] = [];
  loading = true;
  searchQuery = '';
  activeTab: 'all' | 'completed' = 'all';
  currentPage = 1;


  readonly LayoutDashboard = LayoutDashboard;
  readonly UserCircle = UserCircle;
  readonly Calendar = Calendar;
  readonly Menu = Menu;
  readonly User = User;
  readonly ChevronDown = ChevronDown;
  readonly Search = Search;
  readonly Moon = Moon;
  readonly Sun = Sun;
  readonly LogOut = LogOut;
  readonly Key = Key;

  ngOnInit(): void {
    const storedName = localStorage.getItem('userName');
    if (storedName) {
      this.studentName = storedName;
    }
    this.loadMyEvents();
  }

  /** silent: background auto-refresh (no spinner, no error dialogs). */
  loadMyEvents(silent = false): void {
    if (!silent) this.loading = true;
    this.http.get<any>('http://localhost:8000/api/student/my-events', { withCredentials: true })
      .subscribe({
        next: (response) => {
          this.events = (response.events || []).map((evt: any) => ({
            id: evt.id,
            title: evt.event_name,
            date: evt.event_date,
            time: formatTimeRange(evt.event_time, evt.event_end_time),
            venue: evt.venue,
            attendance: ['present', 'not_recorded'].includes(evt.attendance) ? evt.attendance : 'pending',
          }));
          this.loading = false;
        },
        error: (error) => {
          if (silent) return;  // keep showing the last list
          this.loading = false;
          this.events = [];
          if (error.status === 401) {
            this.dialog.error('Session Expired', 'Please log in again to see your events.');
          } else {
            this.dialog.error('Something went wrong', error.error?.detail || 'Could not load your events.');
          }
        }
      });
  }

  readonly attendanceLabels = { present: 'Present', not_recorded: 'Not Recorded', pending: 'Pending' };

  /** "Completed" = events where your attendance was recorded as Present. */
  get completedCount(): number {
    return this.events.filter(e => e.attendance === 'present').length;
  }

  get filteredEvents(): MyEvent[] {
    const query = this.searchQuery.trim().toLowerCase();
    return this.events.filter(e =>
      (this.activeTab === 'all' || e.attendance === 'present') &&
      (!query || e.title.toLowerCase().includes(query))
    );
  }

  get totalPages(): number {
    return Math.max(1, Math.ceil(this.filteredEvents.length / PAGE_SIZE));
  }

  get pagedEvents(): MyEvent[] {
    const page = Math.min(this.currentPage, this.totalPages);
    return this.filteredEvents.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  }

  setTab(tab: 'all' | 'completed'): void {
    this.activeTab = tab;
    this.currentPage = 1;
  }

  onSearch(): void {
    this.currentPage = 1;
  }

  prevPage(): void {
    if (this.currentPage > 1) this.currentPage--;
  }

  nextPage(): void {
    if (this.currentPage < this.totalPages) this.currentPage++;
  }

  viewEventDetails(event: MyEvent): void {
    this.router.navigate(['/event', event.id]);
  }

  goToDashboard(): void {
    this.router.navigate(['/student-dashboard']);
  }

  goToProfile(): void {
    this.router.navigate(['/student-profile']);
  }

  toggleSidebar(): void {
    this.sidebarOpen = !this.sidebarOpen;
  }

  toggleDropdown(): void {
    this.showDropdown = !this.showDropdown;
  }

  toggleDarkMode(): void {
    this.themeService.toggleDarkMode();
  }

  signOut(): void {
    localStorage.removeItem('userToken');
    localStorage.removeItem('userRole');
    localStorage.removeItem('userName');
    this.router.navigate(['/login']);
  }


  /** Change Password: email a Set New Password link to the logged-in user's email. */
  openChangePassword(): void {
    this.showDropdown = false;
    this.changePasswordService.sendLink();
  }


}
