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
import { SessionService } from '../../services/session.service';
import { ChangePasswordService } from '../../services/change-password.service';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';
import { Paginator } from '../../utils/paginator';
import { DisplayCasePipe } from '../../utils/display-case.pipe';
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
  status: 'present' | 'not_recorded' | 'pending';  // pending = not marked yet
  type: 'student' | 'participant';
}

@Component({
  selector: 'app-organizer-attendance',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective, DisplayCasePipe, SelectComponent],
  templateUrl: './organizer-attendance.html',
  styleUrl: './organizer-attendance.css'
})
export class OrganizerAttendance implements OnInit {
  readonly pager = new Paginator(10); // 10 rows per page
  private dialog = inject(DialogService);
  private session = inject(SessionService);
  readonly filterOptions: SelectOption[] = [{ value: '', label: 'All' }, { value: 'student', label: 'Student' }, { value: 'participant', label: 'Participant' }];
  private changePasswordService = inject(ChangePasswordService);
  showDropdown = false;
  sidebarOpen = true;
  organizerName = 'Juan Dela Cruz';
  
  searchQuery = '';
  selectedFilter = '';
  
  attendees: Attendee[] = [];
  currentPage = 1;
  totalPages = 1;

  
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

  setAttendance(attendee: Attendee, status: Attendee['status']): void {
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
    this.session.signOut();
  }

  goToDashboard(): void {
    this.router.navigate(['/organizer-dashboard']);
  }

  goToEvents(): void {
    this.router.navigate(['/organizer-events']);
  }


  /** Change Password: email a Set New Password link to the logged-in user's email. */
  openChangePassword(): void {
    this.showDropdown = false;
    this.changePasswordService.sendLink();
  }


}
