import { Component, OnInit, ChangeDetectorRef, inject } from '@angular/core';
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
import { registrationOpensOn, isRegistrationOpen, formatShortDate, displayStatus } from '../../utils/registration';

import { DialogService } from '../../services/dialog.service';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';
import { PasswordChecklist } from '../password-checklist/password-checklist';
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
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective, PasswordChecklist],
  templateUrl: './student-dashboard.html',
  styleUrl: './student-dashboard.css'
})
export class StudentDashboard implements OnInit {
  private dialog = inject(DialogService);
  showDropdown = false;
  sidebarOpen = true;
  studentName = 'Juan Dela Cruz';
  roleLabel = localStorage.getItem('userRole') === 'participant' ? 'Participant' : 'Student';
  showChangePasswordModal = false;
  
  searchQueryLeft = '';
  selectedStatusLeft = '';
  searchQueryRight = '';
  
  events: Event[] = [];
  upcomingEvents: Event[] = [];

  passwordForm = {
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  };
  
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
    localStorage.removeItem('userToken');
    localStorage.removeItem('userRole');
    localStorage.removeItem('userName');
    this.router.navigate(['/login']);
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

  openChangePassword(): void {
    this.showChangePasswordModal = true;
    this.showDropdown = false;
  }

  closeChangePassword(): void {
    this.showChangePasswordModal = false;
    this.passwordForm = {
      currentPassword: '',
      newPassword: '',
      confirmPassword: ''
    };
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
      next: (response) => {
        this.dialog.success('Success!', 'Password changed successfully!');
        this.closeChangePassword();
      },
      error: (error) => {
        console.error('Error changing password:', error);
        this.dialog.error('Something went wrong', error.error?.detail || 'Failed to change password. Please check your current password.');
      }
    });
  }
}
