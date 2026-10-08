import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SelectComponent, SelectOption } from '../select/select';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { 
  LucideAngularModule, 
  LayoutDashboard, 
  Calendar, 
  User, 
  Users,
  Menu, 
  Moon, Sun, 
  LogOut, 
  ChevronDown,
  CalendarCheck,
  CalendarX2,
  Key,
  GraduationCap
} from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';

import { DialogService } from '../../services/dialog.service';
import { SessionService } from '../../services/session.service';
import { DisplayCasePipe } from '../../utils/display-case.pipe';
import { autoRefresh } from '../../utils/auto-refresh';
import { ChangePasswordService } from '../../services/change-password.service';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';
interface OrganizerStats {
  students: number;
  participants: number;
  totalEnrollment: number;
  openEvents: number;
}

interface EnrollmentEvent {
  eventId: number;
  eventName: string;
  enrolled: number;
  capacity: number;
  present: number;
}

interface AttendanceData {
  present: number;
  notRecorded: number;
}

/**
 * Organizer Dashboard Component
 * Dashboard view for organizer accounts created by admin
 */
@Component({
  selector: 'app-organizer-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective, DisplayCasePipe, SelectComponent],
  templateUrl: './organizer-dashboard.html',
  styleUrl: './organizer-dashboard.css'
})
export class OrganizerDashboard implements OnInit {
  private dialog = inject(DialogService);
  private session = inject(SessionService);
  /** Re-fetch every 10s so statuses (Open / Full / Closed / Upcoming) update without a reload. */
  private autoRefresh = autoRefresh(() => this.loadDashboardStats());
  private changePasswordService = inject(ChangePasswordService);
  showDropdown = false;
  sidebarOpen = true;
  organizerName = 'Juan De la Cruz';
  
  stats: OrganizerStats = {
    students: 0,
    participants: 0,
    totalEnrollment: 0,
    openEvents: 0
  };
  
  enrollmentData: EnrollmentEvent[] = [];
  
  /** All of the organizer's events together (from the API) */
  attendanceData: AttendanceData = {
    present: 0,
    notRecorded: 0
  };

  /** Attendance Summary filter: '' = all events, otherwise an event id (as text, like every <app-select> value) */
  selectedAttendanceEvent = '';
  attendanceEventOptions: SelectOption[] = [{ value: '', label: 'All Events' }];

  
  // Lucide icons
  readonly LayoutDashboard = LayoutDashboard;
  readonly Calendar = Calendar;
  readonly User = User;
  readonly Users = Users;
  readonly GraduationCap = GraduationCap;
  readonly Menu = Menu;
  readonly Moon = Moon;
  readonly Sun = Sun;
  readonly LogOut = LogOut;
  readonly ChevronDown = ChevronDown;
  readonly CalendarCheck = CalendarCheck;
  readonly CalendarX2 = CalendarX2;
  readonly Key = Key;

  constructor(
    private router: Router, 
    public themeService: ThemeService,
    private http: HttpClient
  ) {}

  ngOnInit(): void {
    // Load organizer name from storage or API
    const storedName = localStorage.getItem('organizerName');
    if (storedName) {
      this.organizerName = storedName;
    }
    
    // Load dashboard stats
    this.loadDashboardStats();
  }

  /**
   * Load dashboard statistics from API
   */
  loadDashboardStats(): void {
    // This would typically fetch from API
    // For now, showing empty state with 0 values
    const organizerId = localStorage.getItem('organizerId') || localStorage.getItem('userId') || '';
    this.http.get<any>('http://localhost:8000/api/organizer/stats', { params: { organizer_id: organizerId } })
      .subscribe({
        next: (response) => {
          this.stats = response.stats;
          this.enrollmentData = response.enrollmentData || [];
          this.attendanceData = response.attendanceData || { present: 0, notRecorded: 0 };
          this.attendanceEventOptions = [
            { value: '', label: 'All Events' },
            ...this.enrollmentData.map(e => ({ value: String(e.eventId), label: e.eventName }))
          ];
          // The chosen event was deleted: go back to all events
          if (this.selectedAttendanceEvent !== '' && !this.enrollmentData.some(e => String(e.eventId) === this.selectedAttendanceEvent)) {
            this.selectedAttendanceEvent = '';
          }
        },
        error: (error) => {
          console.log('No data available, showing empty state');
          // Keep default empty values
        }
      });
  }

  /** Attendance for the event picked in the Attendance Summary (or all events) */
  get attendanceSummary(): AttendanceData {
    if (this.selectedAttendanceEvent === '') return this.attendanceData;
    const event = this.enrollmentData.find(e => String(e.eventId) === this.selectedAttendanceEvent);
    return event ? { present: event.present, notRecorded: event.enrolled - event.present } : this.attendanceData;
  }

  /**
   * Calculate stroke dasharray for pie chart
   */
  getStrokeDasharray(): string {
    // Present slice drawn as a stroke on a r=25 circle (circumference 157.08)
    const circumference = 157.08;
    const { present: presentCount, notRecorded } = this.attendanceSummary;
    const total = presentCount + notRecorded;
    const present = total === 0 ? 0 : (presentCount / total) * circumference;
    return `${present} ${circumference}`;
  }

  getEnrollmentPercent(event: EnrollmentEvent): number {
    return event.capacity ? Math.min((event.enrolled / event.capacity) * 100, 100) : 0;
  }

  /**
   * Toggle sidebar visibility
   */
  toggleSidebar(): void {
    this.sidebarOpen = !this.sidebarOpen;
  }

  /**
   * Toggle user dropdown menu visibility
   */
  toggleDropdown(): void {
    this.showDropdown = !this.showDropdown;
  }

  /**
   * Toggle dark mode
   */
  toggleDarkMode(): void {
    this.themeService.toggleDarkMode();
  }

  /**
   * Sign out organizer and navigate back to login
   */
  signOut(): void {
    this.session.signOut();
  }

  /**
   * Navigate to events page
   */
  goToEvents(): void {
    this.router.navigate(['/organizer-events']);
  }


  /** Change Password: email a Set New Password link to the logged-in user's email. */
  openChangePassword(): void {
    this.showDropdown = false;
    this.changePasswordService.sendLink();
  }


}
