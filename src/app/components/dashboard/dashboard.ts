import { Component, OnInit, ChangeDetectorRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { LucideAngularModule, LayoutDashboard, Calendar, User, GraduationCap, Users, Menu, Moon, Sun, LogOut, ChevronDown, UserCheck, CalendarCheck, CalendarX2, CalendarX, Eye, Trash2 } from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';
import { DialogService } from '../../services/dialog.service';

import { ClickOutsideDirective } from '../../directives/click-outside.directive';
import { Paginator } from '../../utils/paginator';
import { displayStatus, registrationOpensOn } from '../../utils/registration';
export interface Event {
  id: number;
  event_name: string;
  event_description: string;
  event_date: string;
  event_time: string;
  venue: string;
  capacity: number;
  status: string;
  cover_photo: string;
  enrolled_count: number;
  registration_start?: string | null;
  registration_end?: string | null;
}

/**
 * Dashboard Component
 * Main administrator dashboard with sidebar navigation and user menu
 */
@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, LucideAngularModule, ClickOutsideDirective],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class Dashboard implements OnInit {
  readonly pager = new Paginator(10); // 10 rows per page
  private dialog = inject(DialogService);
  showDropdown = false;
  sidebarOpen = true;
  events: Event[] = [];
  
  // Statistics
  totalUsers = 0;
  totalEvents = 0;
  openEvents = 0;
  closedEvents = 0;
  
  // Lucide icons
  readonly LayoutDashboard = LayoutDashboard;
  readonly Calendar = Calendar;
  readonly User = User;
  readonly GraduationCap = GraduationCap;
  readonly Users = Users;
  readonly Menu = Menu;
  readonly Moon = Moon;
  readonly Sun = Sun;
  readonly LogOut = LogOut;
  readonly ChevronDown = ChevronDown;
  
  // Stat card icons
  readonly UserCheck = UserCheck;
  readonly CalendarCheck = CalendarCheck;
  readonly CalendarX2 = CalendarX2;
  readonly CalendarX = CalendarX;
  readonly Eye = Eye;
  readonly Trash2 = Trash2;

  /** Upcoming / Open / Full / Closed, as on the organizer's and student's pages. */
  badgeStatus(event: Event): string {
    return displayStatus(event.status, registrationOpensOn(event.registration_start, event.event_date),
      event.enrolled_count || 0, event.capacity, event.registration_end);
  }

  constructor(
    private router: Router, 
    public themeService: ThemeService, 
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    // Use setTimeout to ensure it runs after component is fully initialized
    setTimeout(() => {
      this.loadEvents();
      this.loadStatistics();
    }, 0);
  }

  /**
   * Load events from API
   */
  loadEvents(): void {
    console.log('🔍 Loading events from API...');
    this.http.get<any>('http://localhost:8000/api/events', {
      withCredentials: true
    })
      .subscribe({
        next: (response) => {
          console.log('✅ Events API response:', response);
          this.events = response.events || [];
          console.log('📊 Events loaded:', this.events);
          
          // Calculate event statistics
          this.totalEvents = this.events.length;
          this.openEvents = this.events.filter(e => e.status === 'open').length;
          this.closedEvents = this.events.filter(e => e.status === 'closed').length;
          
          // Force Angular to detect changes
          this.cdr.detectChanges();
        },
        error: (error) => {
          console.error('❌ Error loading events:', error);
          this.events = [];
          this.cdr.detectChanges();
        }
      });
  }

  /**
   * Load user statistics
   */
  loadStatistics(): void {
    // Load students count
    this.http.get<any>('http://localhost:8000/api/students', {
      withCredentials: true
    }).subscribe({
      next: (response) => {
        const studentsCount = response.count || 0;
        
        // Load participants count
        this.http.get<any>('http://localhost:8000/api/participants', {
          withCredentials: true
        }).subscribe({
          next: (response2) => {
            const participantsCount = response2.count || 0;
            
            // Load organizers count
            this.http.get<any>('http://localhost:8000/api/organizers', {
              withCredentials: true
            }).subscribe({
              next: (response3) => {
                const organizersCount = response3.count || 0;
                
                // Total users = students + participants + organizers (NO ADMINS)
                this.totalUsers = studentsCount + participantsCount + organizersCount;
                
                console.log('📊 Statistics:', {
                  totalUsers: this.totalUsers,
                  students: studentsCount,
                  participants: participantsCount,
                  organizers: organizersCount
                });
                
                // Force Angular to detect changes
                this.cdr.detectChanges();
              }
            });
          }
        });
      }
    });
  }

  /**
   * View event details
   */
  viewEvent(eventId: number): void {
    this.router.navigate(['/event', eventId]);
  }

  /**
   * Delete an event (its registrations and attendance cascade in the database)
   */
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
          this.dialog.error('Delete failed', error.error?.detail || 'Could not delete the event. Please try again.');
        }
      });
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
   * Sign out user and navigate back to login
   */
  signOut(): void {
    // Clear any stored authentication data
    localStorage.removeItem('userToken');
    localStorage.removeItem('userRole');
    
    // Navigate to login page
    this.router.navigate(['/login']);
  }

  /**
   * Navigate to organizer page
   */
  goToOrganizer(): void {
    this.router.navigate(['/organizer']);
  }

  /**
   * Navigate to students page
   */
  goToStudents(): void {
    this.router.navigate(['/students']);
  }

  /**
   * Navigate to participants page
   */
  goToParticipants(): void {
    this.router.navigate(['/participants']);
  }
}
