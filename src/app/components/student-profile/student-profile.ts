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
  Pencil,
  Check
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
  address: string;   // participants
  birthday: string;  // participants, YYYY-MM-DD
  age?: string;      // participants, from the birthday (not editable)
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
  /** Participants share this page but have no SR code, department, program or year level. */
  readonly isStudent = localStorage.getItem('userRole') !== 'participant';
  readonly roleLabel = this.isStudent ? 'Student' : 'Participant';

  profile: ProfileData = {
    fullName: '',
    srCode: '',
    collegeDepartment: '',
    program: '',
    yearLevel: '',
    gender: '',
    contactNumber: '',
    address: '',
    birthday: '',
    email: '',
    role: this.roleLabel
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
  readonly Check = Check;

  readonly yearLevels = ['1ST YEAR', '2ND YEAR', '3RD YEAR', '4TH YEAR'];
  /** Birthday picker can't go past today. */
  readonly today = new Date().toLocaleDateString('en-CA');

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
   * Upload the selected picture; it's stored in the database
   */
  onFileSelected(event: any): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';  // so picking the same file again still fires (change)
    if (!file) return;

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

    const formData = new FormData();
    formData.append('avatar', file);
    this.http.post<any>('http://localhost:8000/api/student/profile/avatar', formData, { withCredentials: true })
      .subscribe({
        next: (response) => {
          // The URL doesn't change when the picture is replaced, so bust the cache
          this.profile.avatarUrl = this.avatarSrc(response.avatarUrl, Date.now());
          this.dialog.success('Success!', 'Profile picture updated successfully!');
        },
        error: (error) => {
          console.error('Error uploading profile picture:', error);
          this.dialog.error('Something went wrong', error.error?.detail || 'Failed to upload profile picture');
        }
      });
  }

  /** '/api/users/5/avatar' -> full backend URL ('' when there's no picture). */
  private avatarSrc(path: string | undefined, version?: number): string {
    if (!path) return '';
    if (path.startsWith('http')) return path;
    return `http://localhost:8000${path}${version ? `?v=${version}` : ''}`;
  }

  /**
   * Run an input's text through a filter/formatter and write the result back into the box
   * (ngModel alone won't redraw it when a blocked key leaves the value unchanged).
   */
  clean(event: globalThis.Event, format: (value: string) => string): string {
    const input = event.target as HTMLInputElement;
    const value = format(input.value);
    if (input.value !== value) input.value = value;
    return value;
  }

  /** Digits only, formatted as 0912-345-6789 (max 11 digits). */
  formatContactNumber(value: string): string {
    const digits = (value || '').replace(/\D/g, '').slice(0, 11);
    if (digits.length <= 4) return digits;
    if (digits.length <= 7) return `${digits.slice(0, 4)}-${digits.slice(4)}`;
    return `${digits.slice(0, 4)}-${digits.slice(4, 7)}-${digits.slice(7)}`;
  }

  /** Digits only, formatted as 23-30046 (max 7 digits). */
  formatSrCode(value: string): string {
    const digits = (value || '').replace(/\D/g, '').slice(0, 7);
    return digits.length <= 2 ? digits : `${digits.slice(0, 2)}-${digits.slice(2)}`;
  }

  /** Letters (including Ñ), spaces and the . - ' found in names; no digits or symbols. */
  lettersOnly(value: string): string {
    return (value || '').replace(/[^A-Za-zÑñ .'-]/g, '').replace(/ {2,}/g, ' ');
  }

  /** Whole years since the birthday ('' when there's none or it's in the future). */
  ageFrom(birthday: string): string {
    const [y, m, d] = (birthday || '').split('-').map(Number);
    if (!y || !m || !d) return '';
    const now = new Date();
    const age = now.getFullYear() - y - ((now.getMonth() + 1 < m || (now.getMonth() + 1 === m && now.getDate() < d)) ? 1 : 0);
    return age >= 0 ? String(age) : '';
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
      avatarUrl: this.avatarSrc(profile.avatarUrl),
      fullName: upper(this.lettersOnly(profile.fullName)),
      srCode: this.formatSrCode(profile.srCode),
      collegeDepartment: upper(this.lettersOnly(profile.collegeDepartment)),
      program: upper(this.lettersOnly(profile.program)),
      yearLevel: this.toYearLevel(profile.yearLevel),
      gender: upper(profile.gender),
      contactNumber: this.formatContactNumber(profile.contactNumber),
      address: upper(profile.address),
    };
  }

  /** '2000-01-05' -> 'JANUARY 5, 2000' (shown when not editing). */
  formatBirthday(value: string): string {
    const [y, m, d] = (value || '').split('-').map(Number);
    if (!y || !m || !d) return '';
    return new Date(y, m - 1, d)
      .toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
      .toUpperCase();
  }
}
