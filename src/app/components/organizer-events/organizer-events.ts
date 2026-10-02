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
  Plus,
  Edit,
  Trash2,
  Key
} from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';
import { DialogService } from '../../services/dialog.service';

import { finalize } from 'rxjs';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';
import { PasswordChecklist } from '../password-checklist/password-checklist';
import { Paginator } from '../../utils/paginator';
import { displayStatus, registrationOpensOn } from '../../utils/registration';
export interface Event {
  id: number;
  title: string;
  description: string;
  aboutEvent: string;
  date: string;
  time: string;
  venue: string;
  currentCapacity: number;
  maxCapacity: number;
  registrationStart: string;  // YYYY-MM-DD; enrolling opens on this date
  registrationEnd: string;    // YYYY-MM-DD; last day to enroll
  department: string;
  status: string;
  coverPhoto?: string;
}

@Component({
  selector: 'app-organizer-events',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective, PasswordChecklist],
  templateUrl: './organizer-events.html',
  styleUrl: './organizer-events.css'
})
export class OrganizerEvents implements OnInit {
  readonly pager = new Paginator(10); // 10 rows per page
  isSaving = false; // disables the submit button while the request runs
  private dialog = inject(DialogService);
  showDropdown = false;
  showChangePasswordModal = false;
  sidebarOpen = true;
  organizerName = 'Juan Dela Cruz';
  
  searchQuery = '';
  selectedStatus = '';
  showCreateModal = false;
  editingEventId: number | null = null;
  
  events: Event[] = [];
  currentPage = 1;
  totalPages = 1;
  
  newEvent = {
    title: '',
    description: '',
    aboutEvent: '',
    date: '',
    time: '',
    endTime: '',
    venue: '',
    capacity: 0,
    registrationStart: '',
    registrationEnd: '',
    department: '',
    coverPhoto: null as File | null
  };

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
  readonly Plus = Plus;
  readonly Edit = Edit;
  readonly Trash2 = Trash2;
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
    
    this.loadEvents();
  }

  get filteredEvents(): Event[] {
    return this.events.filter(event => {
      const matchesSearch = event.title.toLowerCase().includes(this.searchQuery.toLowerCase());
      const matchesStatus = !this.selectedStatus || event.status.toLowerCase() === this.selectedStatus.toLowerCase();
      return matchesSearch && matchesStatus;
    });
  }

  loadEvents(): void {
    // Load events from API
    this.http.get<any>('http://localhost:8000/api/events')
      .subscribe({
        next: (response) => {
          this.events = response.events.map((evt: any) => ({
            id: evt.id,
            title: evt.event_name,
            description: evt.event_description,
            aboutEvent: evt.event_description,
            date: evt.event_date,
            time: evt.event_time,
            venue: evt.venue,
            currentCapacity: evt.enrolled_count || 0,
            maxCapacity: evt.capacity,
            registrationStart: evt.registration_start || '',
            registrationEnd: evt.registration_end || '',
            department: '',
            status: displayStatus(evt.status, registrationOpensOn(evt.registration_start, evt.event_date), evt.enrolled_count || 0, evt.capacity, evt.registration_end),
            coverPhoto: evt.cover_photo ? `http://localhost:8000${evt.cover_photo}` : ''
          })) || [];
        },
        error: (error) => {
          console.log('No events yet or error loading:', error);
          this.events = [];
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

  goToAttendance(): void {
    this.router.navigate(['/organizer-attendance']);
  }

  openCreateModal(): void {
    this.showCreateModal = true;
  }

  closeCreateModal(): void {
    this.showCreateModal = false;
    this.editingEventId = null;
    this.resetForm();
  }

  resetForm(): void {
    this.newEvent = {
      title: '',
      description: '',
      aboutEvent: '',
      date: '',
      time: '',
      endTime: '',
      venue: '',
      capacity: 0,
      registrationStart: '',
    registrationEnd: '',
      department: '',
      coverPhoto: null
    };
  }

  onFileSelected(event: any): void {
    const file = event.target.files[0];
    if (file) {
      this.newEvent.coverPhoto = file;
    }
  }

  createEvent(): void {
    // "HH:MM" strings compare correctly as text
    if (!this.newEvent.time || !this.newEvent.endTime) {
      this.dialog.error('Check your input', 'Please enter the start and end time.');
      return;
    }
    if (this.newEvent.endTime <= this.newEvent.time) {
      this.dialog.error('Check your input', 'End time must be after the start time.');
      return;
    }
    // "YYYY-MM-DD" strings compare correctly as text
    const { registrationStart, registrationEnd, date } = this.newEvent;
    if (!registrationStart || !registrationEnd) {
      this.dialog.error('Check your input', 'Please enter the registration start and end dates.');
      return;
    }
    if (registrationEnd < registrationStart) {
      this.dialog.error('Check your input', "Registration end can't be before the registration start.");
      return;
    }
    if (date && registrationEnd > date) {
      this.dialog.error('Check your input', 'Registration must end on or before the event date.');
      return;
    }

    const formData = new FormData();
    formData.append('event_name', this.newEvent.title);
    formData.append('event_description', this.newEvent.description);
    formData.append('event_date', this.newEvent.date);
    formData.append('event_time', this.newEvent.time);
    formData.append('event_end_time', this.newEvent.endTime);
    formData.append('registration_start', this.newEvent.registrationStart);
    formData.append('registration_end', this.newEvent.registrationEnd);
    formData.append('venue', this.newEvent.venue);
    formData.append('department', this.newEvent.department);
    formData.append('about_event', this.newEvent.aboutEvent);
    formData.append('capacity', this.newEvent.capacity.toString());
    formData.append('organizer_id', localStorage.getItem('organizerId') || localStorage.getItem('userId') || '');
    
    // Add cover photo if selected
    if (this.newEvent.coverPhoto) {
      formData.append('cover_photo', this.newEvent.coverPhoto);
    }
    
    const editing = this.editingEventId !== null;
    const request = editing
      ? this.http.put<any>(`http://localhost:8000/api/events/${this.editingEventId}`, formData)
      : this.http.post<any>('http://localhost:8000/api/events', formData);

    this.isSaving = true;
    request.pipe(finalize(() => (this.isSaving = false))).subscribe({
      next: () => {
        this.loadEvents();
        this.closeCreateModal();
        this.dialog.success('Success!', editing ? 'Event updated successfully!' : 'Event created successfully!');
      },
      error: (error) => {
        console.error('Error saving event:', error);
        this.dialog.error('Something went wrong',
          (editing ? 'Error updating event: ' : 'Error creating event: ') + (error.error?.detail || 'Please try again.'));
      }
    });
  }

  editEvent(event: Event): void {
    // Load the full event so the form starts with its current values
    this.http.get<any>(`http://localhost:8000/api/events/${event.id}`)
      .subscribe({
        next: (response) => {
          const evt = response.event;
          this.newEvent = {
            title: evt.event_name || '',
            description: evt.event_description || '',
            aboutEvent: evt.about_event || '',
            date: evt.event_date || '',
            time: (evt.event_time || '').slice(0, 5),
            endTime: (evt.event_end_time || '').slice(0, 5),
            venue: evt.venue || '',
            capacity: evt.capacity || 0,
            registrationStart: evt.registration_start || '',
            registrationEnd: evt.registration_end || '',
            department: evt.department || '',
            coverPhoto: null
          };
          this.editingEventId = event.id;
          this.showCreateModal = true;
        },
        error: (error) => {
          console.error('Error loading event:', error);
          this.dialog.error('Something went wrong', error.error?.detail || 'Could not load the event.');
        }
      });
  }

  async deleteEvent(eventId: number): Promise<void> {
    const confirmed = await this.dialog.confirm('Warning', 'Are you sure you want to delete this event?');
    if (!confirmed) return;

    this.http.delete(`http://localhost:8000/api/events/${eventId}`)
      .subscribe({
        next: () => {
          this.dialog.success('Deleted!', 'Event deleted successfully.');
          this.loadEvents();
        },
        error: (error) => {
          console.error('Error deleting event:', error);
          this.dialog.error('Delete failed', error.error?.detail || error.error?.message || 'Could not delete the event. Please try again.');
        }
      });
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
