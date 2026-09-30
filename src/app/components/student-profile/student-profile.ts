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
  Moon, Sun,
  LogOut,
  Key,
  Pencil
} from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';

import { DialogService } from '../../services/dialog.service';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';
export interface ProfileData {
  fullName: string;
  srCode: string;
  collegeDepartment: string;
  program: string;
  yearLevel: string;
  gender: string;
  contactNumber: string;
  email: string;
  role: string;
  avatarUrl?: string;  // Add avatar URL field
}

@Component({
  selector: 'app-student-profile',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective],
  templateUrl: './student-profile.html',
  styleUrl: './student-profile.css'
})
export class StudentProfile implements OnInit {
  private dialog = inject(DialogService);
  showDropdown = false;
  sidebarOpen = true;
  isEditing = false;
  
  profile: ProfileData = {
    fullName: '',
    srCode: '',
    collegeDepartment: '',
    program: '',
    yearLevel: '',
    gender: '',
    contactNumber: '',
    email: '',
    role: 'Student'
  };
  
  // Lucide icons
  readonly LayoutDashboard = LayoutDashboard;
  readonly UserCircle = UserCircle;
  readonly Calendar = Calendar;
  readonly Menu = Menu;
  readonly User = User;
  readonly ChevronDown = ChevronDown;
  readonly Moon = Moon;
  readonly Sun = Sun;
  readonly LogOut = LogOut;
  readonly Key = Key;
  readonly Pencil = Pencil;

  readonly yearLevels = ['1ST YEAR', '2ND YEAR', '3RD YEAR', '4TH YEAR'];

  constructor(
    private router: Router,
    private http: HttpClient,
    public themeService: ThemeService
  ) {}

  ngOnInit(): void {
    this.loadProfile();
  }

  loadProfile(): void {
    // Load profile from API or localStorage
    const storedName = localStorage.getItem('userName');
    if (storedName) {
      this.profile.fullName = storedName;
    }

    // TODO: Load full profile from API
    this.http.get<any>('http://localhost:8000/api/student/profile', { withCredentials: true })
      .subscribe({
        next: (response) => {
          this.profile = this.normalizeProfile({ ...this.profile, ...response.profile });
        },
        error: (error) => {
          console.log('Using default profile data');
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
    localStorage.removeItem('userName');
    this.router.navigate(['/login']);
  }

  goToDashboard(): void {
    this.router.navigate(['/student-dashboard']);
  }

  goToMyEvents(): void {
    this.router.navigate(['/my-events']);
  }

  toggleEdit(): void {
    this.isEditing = !this.isEditing;
    if (!this.isEditing) {
      // Save changes
      this.saveProfile();
    }
  }

  saveProfile(): void {
    this.profile = this.normalizeProfile(this.profile);
    this.http.put<any>('http://localhost:8000/api/student/profile', this.profile, { withCredentials: true })
      .subscribe({
        next: (response) => {
          this.profile = this.normalizeProfile({ ...this.profile, ...response.profile });
          localStorage.setItem('userName', this.profile.fullName);
          this.dialog.success('Success!', 'Profile updated successfully!');
        },
        error: (error) => {
          console.error('Error updating profile:', error);
          this.dialog.error('Something went wrong', error.error?.detail || 'Failed to update profile');
        }
      });
  }

  openChangePassword(): void {
    // Navigate to change password or open modal
    console.log('Change password');
  }

  /**
   * Trigger file input click
   */
  triggerFileInput(): void {
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    if (fileInput) {
      fileInput.click();
    }
  }

  /**
   * Handle file selection and preview
   */
  onFileSelected(event: any): void {
    const file = event.target.files[0];
    if (file) {
      // Validate file type
      if (!file.type.startsWith('image/')) {
        this.dialog.error('Check your input', 'Please select an image file');
        return;
      }

      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        this.dialog.error('Check your input', 'Image size must be less than 5MB');
        return;
      }

      // Create preview URL
      const reader = new FileReader();
      reader.onload = (e: any) => {
        this.profile.avatarUrl = e.target.result;
        console.log('Image uploaded:', file.name);
        // TODO: Upload to server
      };
      reader.readAsDataURL(file);
    }
  }

  /** Digits only, formatted as 0912-345-6789 (max 11 digits). */
  formatContactNumber(value: string): string {
    const digits = (value || '').replace(/\D/g, '').slice(0, 11);
    if (digits.length <= 4) return digits;
    if (digits.length <= 7) return `${digits.slice(0, 4)}-${digits.slice(4)}`;
    return `${digits.slice(0, 4)}-${digits.slice(4, 7)}-${digits.slice(7)}`;
  }

  /** Map old values like "1st", "2" or "3rd yr" onto the dropdown's "3RD YEAR" form. */
  private toYearLevel(value: string): string {
    const match = (value || '').match(/[1-4]/);
    return match ? this.yearLevels[Number(match[0]) - 1] : '';
  }

  /** Everything is stored in ALL CAPS; the number is formatted. */
  private normalizeProfile(profile: ProfileData): ProfileData {
    const upper = (v: string) => (v || '').trim().toUpperCase();
    return {
      ...profile,
      fullName: upper(profile.fullName),
      srCode: upper(profile.srCode),
      collegeDepartment: upper(profile.collegeDepartment),
      program: upper(profile.program),
      yearLevel: this.toYearLevel(profile.yearLevel),
      gender: upper(profile.gender),
      contactNumber: this.formatContactNumber(profile.contactNumber),
    };
  }
}
