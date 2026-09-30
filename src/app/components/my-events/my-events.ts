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
import { DialogService } from '../../services/dialog.service';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';
import { PasswordChecklist } from '../password-checklist/password-checklist';

export interface MyEvent {
  id: number;
  title: string;
  date: string | null;
  time: string | null;
  venue: string;
  attendance: 'present' | 'not_recorded';
}

const PAGE_SIZE = 10;

/**
 * "My Events" for students and participants: the events they enrolled in, with
 * their attendance. Shares the Student Dashboard's sidebar, top bar and styles.
 */
@Component({
  selector: 'app-my-events',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective, PasswordChecklist],
  templateUrl: './my-events.html',
  styleUrls: ['../student-dashboard/student-dashboard.css', './my-events.css']
})
export class MyEvents implements OnInit {
  private dialog = inject(DialogService);
  private router = inject(Router);
  private http = inject(HttpClient);
  readonly themeService = inject(ThemeService);

  showDropdown = false;
  sidebarOpen = true;
  studentName = 'Student';
  readonly roleLabel = localStorage.getItem('userRole') === 'participant' ? 'Participant' : 'Student';
  readonly isStudent = localStorage.getItem('userRole') !== 'participant';
  showChangePasswordModal = false;

  events: MyEvent[] = [];
  loading = true;
  searchQuery = '';
  activeTab: 'all' | 'completed' = 'all';
  currentPage = 1;

  passwordForm = { currentPassword: '', newPassword: '', confirmPassword: '' };

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

  loadMyEvents(): void {
    this.loading = true;
    this.http.get<any>('http://localhost:8000/api/student/my-events', { withCredentials: true })
      .subscribe({
        next: (response) => {
          this.events = (response.events || []).map((evt: any) => ({
            id: evt.id,
            title: evt.event_name,
            date: evt.event_date,
            time: evt.event_time,
            venue: evt.venue,
            attendance: evt.attendance === 'present' ? 'present' : 'not_recorded',
          }));
          this.loading = false;
        },
        error: (error) => {
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

  /** "14:30:00" -> "2:30 PM" */
  formatTime(time: string | null): string {
    if (!time) return 'TBA';
    const [h, m] = time.split(':');
    const hour = Number(h);
    return `${hour % 12 || 12}:${m} ${hour >= 12 ? 'PM' : 'AM'}`;
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

  openChangePassword(): void {
    this.showChangePasswordModal = true;
    this.showDropdown = false;
  }

  closeChangePassword(): void {
    this.showChangePasswordModal = false;
    this.passwordForm = { currentPassword: '', newPassword: '', confirmPassword: '' };
  }

  changePassword(): void {
    if (this.passwordForm.newPassword !== this.passwordForm.confirmPassword) {
      this.dialog.error('Check your input', 'New passwords do not match!');
      return;
    }
    this.http.post<any>('http://localhost:8000/api/student/change-password', {
      current_password: this.passwordForm.currentPassword,
      new_password: this.passwordForm.newPassword
    }, { withCredentials: true }).subscribe({
      next: () => {
        this.dialog.success('Success!', 'Password changed successfully!');
        this.closeChangePassword();
      },
      error: (error) => {
        this.dialog.error('Something went wrong',
          error.error?.detail || 'Failed to change password. Please check your current password.');
      }
    });
  }
}
