import { Component, OnInit, ChangeDetectorRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { 
  LucideAngularModule, 
  Menu,
  User,
  ChevronDown,
  ArrowLeft,
  Loader2,
  Calendar,
  MapPin,
  Building2
} from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';

import { DialogService } from '../../services/dialog.service';
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
}

@Component({
  selector: 'app-event-details',
  standalone: true,
  imports: [CommonModule, LucideAngularModule, ClickOutsideDirective],
  templateUrl: './event-details.html',
  styleUrl: './event-details.css'
})
export class EventDetails implements OnInit {
  private dialog = inject(DialogService);
  showDropdown = false;
  studentName = 'Juan Dela Cruz';
  eventId: number | null = null;
  event: EventDetail | null = null;
  loading = true;
  
  // Lucide icons
  readonly Menu = Menu;
  readonly User = User;
  readonly ChevronDown = ChevronDown;
  readonly ArrowLeft = ArrowLeft;
  readonly Loader2 = Loader2;
  readonly Calendar = Calendar;
  readonly MapPin = MapPin;
  readonly Building2 = Building2;

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
      }
    });
  }

  loadEventDetails(): void {
    console.log('Loading event ID:', this.eventId);
    
    this.http.get<any>(`http://localhost:8000/api/events/${this.eventId}`)
      .subscribe({
        next: (response) => {
          console.log('Event response received:', response);
          
          if (!response.success || !response.event) {
            console.error('Invalid response format:', response);
            this.loading = false;
            this.cdr.detectChanges();
            this.dialog.error('Something went wrong', 'Event not found.');
            return;
          }
          
          // Map backend response to frontend format
          const evt = response.event;
          console.log('Mapping event:', evt);
          
          // Format time to 12-hour format
          let formattedTime = 'TBA';
          if (evt.event_time) {
            try {
              const timeStr = evt.event_time;
              const [hours, minutes] = timeStr.split(':');
              const hour = parseInt(hours);
              const ampm = hour >= 12 ? 'PM' : 'AM';
              const hour12 = hour % 12 || 12;
              formattedTime = `${hour12}:${minutes} ${ampm}`;
              console.log('Formatted time:', formattedTime);
            } catch (e) {
              console.error('Error formatting time:', e);
            }
          }
          
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
            coverPhoto: evt.cover_photo
          };
          
          console.log('Event mapped successfully:', this.event);
          this.loading = false;
          this.cdr.detectChanges();
        },
        error: (error) => {
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
    localStorage.removeItem('userToken');
    localStorage.removeItem('userRole');
    localStorage.removeItem('userName');
    this.router.navigate(['/login']);
  }

  backToDashboard(): void {
    this.router.navigate(['/student-dashboard']);
  }

  enrollInEvent(): void {
    if (!this.event) return;

    const userEmail = localStorage.getItem('userEmail');
    if (!userEmail) {
      this.dialog.error('Please Log In Again', 'Please login again to enroll.');
      return;
    }

    const formData = new FormData();
    formData.append('student_email', userEmail);

    this.http.post<any>(`http://localhost:8000/api/events/${this.eventId}/enroll`, formData)
      .subscribe({
        next: (response) => {
          this.dialog.success('Success!', 'Successfully enrolled in event!');
          this.loadEventDetails(); // Reload to update capacity
        },
        error: (error) => {
          console.error('Error enrolling:', error);
          const errorMsg = error.error?.detail || 'Failed to enroll. Please try again.';
          this.dialog.error('Something went wrong', errorMsg);
        }
      });
  }
}
