import { Component, OnInit, ChangeDetectorRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { 
  LucideAngularModule, 
  Menu,
  LayoutDashboard,
  GraduationCap,
  Users,
  UserCircle,
  User,
  ChevronDown,
  ArrowLeft,
  Loader2,
  Calendar,
  MapPin,
  Building2,
  CalendarClock
} from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';
import { formatTimeRange } from '../../utils/event-time';
import { registrationOpensOn, isRegistrationOpen, isRegistrationOver, formatShortDate } from '../../utils/registration';

import { DialogService } from '../../services/dialog.service';
import { SessionService } from '../../services/session.service';
import { DisplayCasePipe } from '../../utils/display-case.pipe';
import { autoRefresh } from '../../utils/auto-refresh';
import { coverInitial, coverColor } from '../../utils/cover-placeholder';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';
export interface EventDetail {
  id: number;
  title: string;
  description: string;
  aboutEvent: string;
  date: string;
  time: string;
  venue: string;
  department: string;
  totalCapacity: number;
  currentlyEnrolled: number;
  slotsAvailable: number;
  status: string;
  coverPhoto?: string;
  opensOn: string;  // YYYY-MM-DD enrolling opens (registration start, or the event date)
  closesOn: string; // YYYY-MM-DD last day to enroll ('' = until the event ends)
}

@Component({
  selector: 'app-event-details',
  standalone: true,
  imports: [CommonModule, LucideAngularModule, ClickOutsideDirective, DisplayCasePipe],
  templateUrl: './event-details.html',
  styleUrl: './event-details.css'
})
export class EventDetails implements OnInit {
  /** Only students and participants can enroll; admins open this page from their Dashboard just to view. */
  readonly canEnroll = ['student', 'participant'].includes(localStorage.getItem('userRole') || '');
  private dialog = inject(DialogService);
  private session = inject(SessionService);
  /** Re-fetch every 10s so statuses (Open / Full / Closed / Upcoming) update without a reload. */
  private autoRefresh = autoRefresh(() => this.eventId && this.loadEventDetails(true));
  showDropdown = false;
  sidebarOpen = true;
  readonly role = localStorage.getItem('userRole') || '';
  /** Sidebar heading, as on the role's own pages. */
  readonly roleLabel = ({ admin: 'Administrator', organizer: 'Organizer', participant: 'Participant' } as Record<string, string>)[this.role] || 'Student';
  studentName = 'Juan Dela Cruz';
  eventId: number | null = null;
  event: EventDetail | null = null;
  loading = true;
  /** The logged-in student/participant already has a registration for this event. */
  isEnrolled = false;
  /** Set by the organizer on the Attendance page: 'present', 'not_recorded', or 'pending' (not marked yet). */
  attendance: string | null = null;
  /** An enroll/cancel request is in flight (blocks double clicks). */
  enrollBusy = false;
  
  // Lucide icons
  readonly Menu = Menu;
  readonly LayoutDashboard = LayoutDashboard;
  readonly GraduationCap = GraduationCap;
  readonly Users = Users;
  readonly UserCircle = UserCircle;
  readonly User = User;
  readonly ChevronDown = ChevronDown;
  readonly ArrowLeft = ArrowLeft;
  readonly Loader2 = Loader2;
  readonly Calendar = Calendar;
  readonly MapPin = MapPin;
  readonly Building2 = Building2;
  readonly CalendarClock = CalendarClock;

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private http: HttpClient,
    public themeService: ThemeService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    const storedName = localStorage.getItem('userName');
    if (storedName) {
      this.studentName = storedName;
    }

    // Get event ID from route params
    this.route.params.subscribe(params => {
      this.eventId = +params['id'];
      if (this.eventId) {
        this.loadEventDetails();
        this.loadEnrollment();
      }
    });
  }

  /** silent: background auto-refresh (no error dialogs; keeps the page as it is on failure). */
  loadEventDetails(silent = false): void {
    console.log('Loading event ID:', this.eventId);
    
    this.http.get<any>(`http://localhost:8000/api/events/${this.eventId}`)
      .subscribe({
        next: (response) => {
          console.log('Event response received:', response);
          
          if (!response.success || !response.event) {
            if (silent) return;
            console.error('Invalid response format:', response);
            this.loading = false;
            this.cdr.detectChanges();
            this.dialog.error('Something went wrong', 'Event not found.');
            return;
          }
          
          // Map backend response to frontend format
          const evt = response.event;
          console.log('Mapping event:', evt);
          
          const formattedTime = formatTimeRange(evt.event_time, evt.event_end_time);
          
          this.event = {
            id: evt.id,
            title: evt.event_name,
            description: evt.event_description || 'No description available',
            aboutEvent: evt.about_event || evt.event_description || 'No additional information available',
            date: evt.event_date || 'TBA',
            time: formattedTime,
            venue: evt.venue || 'TBA',
            department: evt.department || '',
            totalCapacity: evt.capacity || 0,
            currentlyEnrolled: evt.enrolled_count || 0,
            slotsAvailable: (evt.capacity || 0) - (evt.enrolled_count || 0),
            status: evt.status || 'open',
            opensOn: registrationOpensOn(evt.registration_start, evt.event_date),
            closesOn: evt.registration_end || '',
            coverPhoto: evt.cover_photo
          };
          
          console.log('Event mapped successfully:', this.event);
          this.loading = false;
          this.cdr.detectChanges();
        },
        error: (error) => {
          if (silent) return;
          console.error('Error loading event:', error);
          console.error('Error details:', error.error);
          console.error('Status:', error.status);
          this.loading = false;
          this.cdr.detectChanges();
          this.dialog.error('Something went wrong', `Failed to load event details: ${error.message}`);
        }
      });
  }

  toggleDropdown(): void {
    this.showDropdown = !this.showDropdown;
  }

  toggleDarkMode(): void {
    this.themeService.toggleDarkMode();
  }

  signOut(): void {
    this.session.signOut();
  }

  toggleSidebar(): void {
    this.sidebarOpen = !this.sidebarOpen;
  }

  goTo(path: string): void {
    this.router.navigate([path]);
  }

  /** Back to Dashboard: each role goes to its own dashboard (admins open this page too). */
  backToDashboard(): void {
    const dashboards: Record<string, string> = {
      admin: '/dashboard',
      organizer: '/organizer-dashboard',
    };
    this.router.navigate([dashboards[localStorage.getItem('userRole') || ''] || '/student-dashboard']);
  }

  /** Whether the logged-in user is already enrolled (decides Enroll vs Cancel Enrollment). */
  loadEnrollment(): void {
    if (!this.canEnroll) return;
    this.http.get<any>(`http://localhost:8000/api/events/${this.eventId}/enrollment`, { withCredentials: true })
      .subscribe({
        next: (response) => {
          this.isEnrolled = !!response.enrolled;
          this.attendance = response.attendance || null;
        },
        error: (error) => console.error('Error checking enrollment:', error)
      });
  }

  /** Upcoming: registration hasn't started yet, so enrolling is blocked. */
  get registrationOpen(): boolean {
    return !!this.event && isRegistrationOpen(this.event.opensOn);
  }

  /** Cancelling is only allowed during the registration period, before attendance is recorded. */
  get canCancel(): boolean {
    return !!this.event && this.event.status === 'open' && this.registrationOpen && !this.registrationOver
      && this.attendance !== 'present';
  }

  /** Past the registration end date: enrolling is closed. */
  get registrationOver(): boolean {
    return !!this.event && isRegistrationOver(this.event.closesOn);
  }

  readonly formatShortDate = formatShortDate;
  readonly coverInitial = coverInitial;
  readonly coverColor = coverColor;

  enrollInEvent(): void {
    if (!this.event || this.isEnrolled || this.enrollBusy || !this.registrationOpen || this.registrationOver) return;

    this.enrollBusy = true;
    this.http.post<any>(`http://localhost:8000/api/events/${this.eventId}/enroll`, null, { withCredentials: true })
      .subscribe({
        next: () => {
          this.enrollBusy = false;
          this.isEnrolled = true;
          this.dialog.success('Success!', 'Successfully enrolled in event!');
          this.loadEventDetails(); // Reload to update capacity
        },
        error: (error) => {
          this.enrollBusy = false;
          console.error('Error enrolling:', error);
          const errorMsg = error.error?.detail || 'Failed to enroll. Please try again.';
          this.dialog.error('Something went wrong', errorMsg);
          this.loadEnrollment(); // e.g. "Already enrolled": show Cancel Enrollment
        }
      });
  }

  async cancelEnrollment(): Promise<void> {
    if (!this.event || !this.isEnrolled || this.enrollBusy || !this.canCancel) return;
    if (!await this.dialog.confirm('Warning', 'Are you sure you want to cancel your enrollment in this event?')) return;

    this.enrollBusy = true;
    this.http.delete<any>(`http://localhost:8000/api/events/${this.eventId}/enroll`, { withCredentials: true })
      .subscribe({
        next: () => {
          this.enrollBusy = false;
          this.isEnrolled = false;
          this.dialog.success('Success!', 'Your enrollment was cancelled.');
          this.loadEventDetails(); // Reload to update capacity
        },
        error: (error) => {
          this.enrollBusy = false;
          console.error('Error cancelling enrollment:', error);
          this.dialog.error('Something went wrong', error.error?.detail || 'Failed to cancel enrollment. Please try again.');
          this.loadEnrollment();
        }
      });
  }
}
