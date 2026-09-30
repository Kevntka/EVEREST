import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
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
  ClipboardList,
  GraduationCap
} from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';

import { DialogService } from '../../services/dialog.service';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';
import { PasswordChecklist } from '../password-checklist/password-checklist';
interface OrganizerStats {
  students: number;
  participants: number;
  totalEnrollment: number;
  openEvents: number;
}

interface EnrollmentEvent {
  eventName: string;
  enrolled: number;
  capacity: number;
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
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective, PasswordChecklist],
  templateUrl: './organizer-dashboard.html',
  styleUrl: './organizer-dashboard.css'
})
export class OrganizerDashboard implements OnInit {
  private dialog = inject(DialogService);
  showDropdown = false;
  showChangePasswordModal = false;
  sidebarOpen = true;
  organizerName = 'Juan De la Cruz';
  
  stats: OrganizerStats = {
    students: 0,
    participants: 0,
    totalEnrollment: 0,
    openEvents: 0
  };
  
  enrollmentData: EnrollmentEvent[] = [];
  
  attendanceData: AttendanceData = {
    present: 0,
    notRecorded: 0
  };

  passwordForm = {
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  };
  
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
  readonly ClipboardList = ClipboardList;

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
        },
        error: (error) => {
          console.log('No data available, showing empty state');
          // Keep default empty values
        }
      });
  }

  /**
   * Calculate stroke dasharray for pie chart
   */
  getStrokeDasharray(): string {
    // Present slice drawn as a stroke on a r=25 circle (circumference 157.08)
    const circumference = 157.08;
    const total = this.attendanceData.present + this.attendanceData.notRecorded;
    const present = total === 0 ? 0 : (this.attendanceData.present / total) * circumference;
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
    // Clear stored authentication data
    localStorage.removeItem('userToken');
    localStorage.removeItem('userRole');
    localStorage.removeItem('organizerName');
    
    // Navigate to login page
    this.router.navigate(['/login']);
  }

  /**
   * Navigate to events page
   */
  goToEvents(): void {
    this.router.navigate(['/organizer-events']);
  }

  /**
   * Navigate to attendance page
   */
  goToAttendance(): void {
    this.router.navigate(['/organizer-attendance']);
  }

  /**
   * Open change password modal
   */
  openChangePassword(): void {
    this.showChangePasswordModal = true;
    this.showDropdown = false;
  }

  /**
   * Close change password modal
   */
  closeChangePassword(): void {
    this.showChangePasswordModal = false;
    this.passwordForm = {
      currentPassword: '',
      newPassword: '',
      confirmPassword: ''
    };
  }

  /**
   * Change password
   */
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
