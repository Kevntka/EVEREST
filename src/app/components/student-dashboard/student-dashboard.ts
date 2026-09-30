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
  selectedStatusRight = '';
  
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
            time: evt.event_time,
            venue: evt.venue,
            availableSlots: evt.capacity - (evt.enrolled_count || 0),
            status: evt.status,
            coverPhoto: evt.cover_photo ? `http://localhost:8000${evt.cover_photo}` : '' // Full URL for image
          })) || [];
          
          console.log('Mapped events:', allEvents); // Debug log
          
          // Events whose start date is after today are "upcoming"; they move to
          // the Events column once their start date arrives (dates are YYYY-MM-DD)
          const now = new Date();
          const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
          this.events = allEvents.filter((evt: Event) => !evt.date || evt.date <= today);
          this.upcomingEvents = allEvents.filter((evt: Event) => evt.date && evt.date > today);
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

  get filteredEvents(): Event[] {
    return this.events.filter(event => {
      const matchesSearch = event.title.toLowerCase().includes(this.searchQueryLeft.toLowerCase());
      const matchesStatus = !this.selectedStatusLeft || event.status.toLowerCase() === this.selectedStatusLeft.toLowerCase();
      return matchesSearch && matchesStatus;
    });
  }

  get filteredUpcomingEvents(): Event[] {
    return this.upcomingEvents.filter(event => {
      const matchesSearch = event.title.toLowerCase().includes(this.searchQueryRight.toLowerCase());
      const matchesStatus = !this.selectedStatusRight || event.status.toLowerCase() === this.selectedStatusRight.toLowerCase();
      return matchesSearch && matchesStatus;
    });
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
