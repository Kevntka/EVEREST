import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { 
  LucideAngularModule, 
  LayoutDashboard, 
  Calendar,
  ClipboardCheck,
  User,
  Menu, 
  Moon, Sun, 
  LogOut, 
  ChevronDown,
  Search,
  Key,
  UserCheck,
  UserMinus
} from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';

import { DialogService } from '../../services/dialog.service';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';
import { PasswordChecklist } from '../password-checklist/password-checklist';
import { Paginator } from '../../utils/paginator';
export interface Attendee {
  id: number;
  name: string;
  department: string;
  gsuite?: string;
  email?: string;
  gender: string;
  contactNumber: string;
  yearLevel?: string;
  eventName: string;
  address?: string;
  status: 'present' | 'not_recorded';
  type: 'student' | 'participant';
}

@Component({
  selector: 'app-organizer-attendance',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective, PasswordChecklist],
  templateUrl: './organizer-attendance.html',
  styleUrl: './organizer-attendance.css'
})
export class OrganizerAttendance implements OnInit {
  readonly pager = new Paginator(10); // 10 rows per page
  private dialog = inject(DialogService);
  showDropdown = false;
  showChangePasswordModal = false;
  sidebarOpen = true;
  organizerName = 'Juan Dela Cruz';
  
  searchQuery = '';
  selectedFilter = '';
  
  attendees: Attendee[] = [];
  currentPage = 1;
  totalPages = 1;

  passwordForm = {
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  };
  
  // Lucide icons
  readonly LayoutDashboard = LayoutDashboard;
  readonly Calendar = Calendar;
  readonly ClipboardCheck = ClipboardCheck;
  readonly User = User;
  readonly Menu = Menu;
  readonly Moon = Moon;
  readonly Sun = Sun;
  readonly LogOut = LogOut;
  readonly ChevronDown = ChevronDown;
  readonly Search = Search;
  readonly UserCheck = UserCheck;
  readonly UserMinus = UserMinus;
  readonly Key = Key;

  constructor(
    private router: Router, 
    public themeService: ThemeService,
    private http: HttpClient
  ) {}

  ngOnInit(): void {
    const storedName = localStorage.getItem('organizerName');
    if (storedName) {
      this.organizerName = storedName;
    }
    
    this.loadAttendees();
  }

  /** Table columns follow the dropdown: participant, student, or all (''). */
  get columnCount(): number {
    return this.selectedFilter === 'student' ? 8 : 7;
  }

  get filteredAttendees(): Attendee[] {
    return this.attendees.filter(attendee => {
      const matchesSearch = attendee.name.toLowerCase().includes(this.searchQuery.toLowerCase());
      const matchesFilter = !this.selectedFilter || attendee.type === this.selectedFilter;
      return matchesSearch && matchesFilter;
    });
  }

  loadAttendees(): void {
    // Load attendees from API
    const organizerId = localStorage.getItem('organizerId') || localStorage.getItem('userId') || '';
    this.http.get<any>('http://localhost:8000/api/organizer/attendees', { params: { organizer_id: organizerId } })
      .subscribe({
        next: (response) => {
          this.attendees = response.attendees || [];
        },
        error: (error) => {
          console.log('No attendees yet or error loading:', error);
          this.attendees = [];
        }
      });
  }

  setAttendance(attendee: Attendee, status: 'present' | 'not_recorded'): void {
    if (attendee.status === status) return;
    this.http.put<any>(`http://localhost:8000/api/organizer/attendees/${attendee.id}/attendance`, { status })
      .subscribe({
        next: () => {
          attendee.status = status;
        },
        error: (error) => {
          console.error('Error updating attendance:', error);
          this.dialog.error('Something went wrong', 'Failed to update attendance: ' + (error.error?.detail || 'Please try again.'));
        }
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
    localStorage.removeItem('organizerName');
    this.router.navigate(['/login']);
  }

  goToDashboard(): void {
    this.router.navigate(['/organizer-dashboard']);
  }

  goToEvents(): void {
    this.router.navigate(['/organizer-events']);
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

    this.http.post<any>('http://localhost:8000/api/organizer/change-password', {
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
