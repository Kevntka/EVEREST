import { Component, OnInit, ChangeDetectorRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SelectComponent, SelectOption } from '../select/select';
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
import { registrationOpensOn, isRegistrationOpen, formatShortDate, displayStatus } from '../../utils/registration';

import { DialogService } from '../../services/dialog.service';
import { SessionService } from '../../services/session.service';
import { DisplayCasePipe } from '../../utils/display-case.pipe';
import { autoRefresh } from '../../utils/auto-refresh';
import { coverInitial, coverColor } from '../../utils/cover-placeholder';
import { ChangePasswordService } from '../../services/change-password.service';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';
export interface Event {
  id: number;
  title: string;
  description: string;
  date: string;
  time: string;
  venue: string;
  availableSlots: number;
  status: string;
  coverPhoto?: string;
  opensOn: string;  // YYYY-MM-DD enrolling opens (registration start, or the event date)
  closesOn: string; // YYYY-MM-DD last day to enroll ('' = until the event ends)
  enrolled: number;
  capacity: number;
}

@Component({
  selector: 'app-student-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective, SelectComponent, DisplayCasePipe],
  templateUrl: './student-dashboard.html',
  styleUrl: './student-dashboard.css'
})
export class StudentDashboard implements OnInit {
  private dialog = inject(DialogService);
  private session = inject(SessionService);
  readonly statusOptions: SelectOption[] = [{ value: '', label: 'Status' }, { value: 'open', label: 'Open' }, { value: 'full', label: 'Full' }, { value: 'closed', label: 'Closed' }];
  /** Re-fetch every 10s so statuses (Open / Full / Closed / Upcoming) update without a reload. */
  private autoRefresh = autoRefresh(() => this.loadEvents());
  private changePasswordService = inject(ChangePasswordService);
  showDropdown = false;
  sidebarOpen = true;
  studentName = 'Juan Dela Cruz';
  roleLabel = localStorage.getItem('userRole') === 'participant' ? 'Participant' : 'Student';
  
  searchQueryLeft = '';
  selectedStatusLeft = '';
  searchQueryRight = '';
  
  events: Event[] = [];
  upcomingEvents: Event[] = [];

  
  // Lucide icons
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
  readonly formatShortDate = formatShortDate;
  readonly coverInitial = coverInitial;
  readonly coverColor = coverColor;

  constructor(
    private router: Router, 
    public themeService: ThemeService,
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    const storedName = localStorage.getItem('userName');
    if (storedName) {
      this.studentName = storedName;
    }
    
    this.loadEvents();
  }

  loadEvents(): void {
    this.http.get<any>('http://localhost:8000/api/events')
      .subscribe({
        next: (response) => {
          console.log('Events loaded:', response); // Debug log
          const allEvents = response.events.map((evt: any) => ({
            id: evt.id,
            title: evt.event_name,
            description: evt.event_description,
            date: evt.event_date,
            time: formatTimeRange(evt.event_time, evt.event_end_time),
            venue: evt.venue,
            availableSlots: evt.capacity - (evt.enrolled_count || 0),
            status: evt.status,
            opensOn: registrationOpensOn(evt.registration_start, evt.event_date),
            closesOn: evt.registration_end || '',
            enrolled: evt.enrolled_count || 0,
            capacity: evt.capacity,
            coverPhoto: evt.cover_photo ? `http://localhost:8000${evt.cover_photo}` : '' // Full URL for image
          })) || [];
          
          console.log('Mapped events:', allEvents); // Debug log
          
          // Events whose registration hasn't started yet are "upcoming" (can't enroll);
          // they move to the Events column on their registration start date
          this.events = allEvents.filter((evt: Event) => isRegistrationOpen(evt.opensOn));
          this.upcomingEvents = allEvents.filter((evt: Event) => !isRegistrationOpen(evt.opensOn));
          this.cdr.detectChanges();
        },
        error: (error) => {
          console.error('Error loading events:', error);
          // Show empty state
          this.events = [];
          this.upcomingEvents = [];
          this.cdr.detectChanges();
        }
      });
  }

  /** Badge shown on a card: Upcoming / Open / Full / Closed (same rule as the organizer's table). */
  badgeStatus(event: Event, _upcoming = false): string {
    return displayStatus(event.status, event.opensOn, event.enrolled, event.capacity, event.closesOn);
  }

  get filteredEvents(): Event[] {
    return this.events.filter(event => {
      const matchesSearch = event.title.toLowerCase().includes(this.searchQueryLeft.toLowerCase());
      const matchesStatus = !this.selectedStatusLeft || this.badgeStatus(event) === this.selectedStatusLeft;
      return matchesSearch && matchesStatus;
    });
  }

  get filteredUpcomingEvents(): Event[] {
    return this.upcomingEvents.filter(event =>
      event.title.toLowerCase().includes(this.searchQueryRight.toLowerCase())
    );
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
    this.session.signOut();
  }

  viewEventDetails(event: Event): void {
    // Navigate to event details page
    this.router.navigate(['/event', event.id]);
  }

  goToProfile(): void {
    this.router.navigate(['/student-profile']);
  }

  goToMyEvents(): void {
    this.router.navigate(['/my-events']);
  }


  /** Change Password: email a Set New Password link to the logged-in user's email. */
  openChangePassword(): void {
    this.showDropdown = false;
    this.changePasswordService.sendLink();
  }


}
