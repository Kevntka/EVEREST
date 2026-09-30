import { Component, OnInit, ChangeDetectorRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { LucideAngularModule, LayoutDashboard, Calendar, User, GraduationCap, Users, Menu, Moon, Sun, LogOut, ChevronDown, Search, Eye, Trash2, Mail, MapPin, Phone, UserRound } from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';
import { DialogService } from '../../services/dialog.service';

import { ClickOutsideDirective } from '../../directives/click-outside.directive';
import { Paginator } from '../../utils/paginator';
export interface Participant {
  id: number;
  full_name: string;
  email: string;
  address: string;
  gender: string;
  contact_number: string;
}

/**
 * Participants Component
 * Manage participants with search and filter capabilities
 */
@Component({
  selector: 'app-participants',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective],
  templateUrl: './participants.html',
  styleUrl: './participants.css'
})
export class Participants implements OnInit {
  readonly pager = new Paginator(10); // 10 rows per page
  private dialog = inject(DialogService);
  showDropdown = false;
  sidebarOpen = true;
  searchName = '';
  participants: Participant[] = [];
  filteredParticipants: Participant[] = [];
  showViewModal = false;
  selectedParticipant: Participant | null = null;
  
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
  readonly Search = Search;
  readonly Eye = Eye;
  readonly Mail = Mail;
  readonly MapPin = MapPin;
  readonly Phone = Phone;
  readonly UserRound = UserRound;
  readonly Trash2 = Trash2;

  constructor(
    private router: Router, 
    public themeService: ThemeService, 
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    // Use setTimeout to ensure it runs after component is fully initialized
    setTimeout(() => {
      this.loadParticipants();
    }, 0);
  }

  /**
   * Load participants from API
   */
  loadParticipants(): void {
    console.log('🔍 Loading participants from API...');
    this.http.get<any>('http://localhost:8000/api/participants', {
      withCredentials: true
    })
      .subscribe({
        next: (response) => {
          console.log('✅ Participants API response:', response);
          this.participants = response.participants || [];
          this.filteredParticipants = this.participants;
          console.log('📊 Participants loaded:', this.participants);
          console.log('📊 Filtered participants:', this.filteredParticipants);
          
          // Force Angular to detect changes
          this.cdr.detectChanges();
        },
        error: (error) => {
          console.error('❌ Error loading participants:', error);
          this.participants = [];
          this.filteredParticipants = [];
          this.cdr.detectChanges();
          this.dialog.error('Something went wrong', 'Error loading participants: ' + (error.message || 'Unknown error'));
        }
      });
  }

  /**
   * Filter participants by search name
   */
  filterParticipants(): void {
    this.filteredParticipants = this.participants.filter(participant => {
      return participant.full_name.toLowerCase().includes(this.searchName.toLowerCase());
    });
  }

  /**
   * View participant details
   */
  viewParticipant(participant: Participant): void {
    this.selectedParticipant = participant;
    this.showViewModal = true;
  }

  /**
   * Close view modal
   */
  closeViewModal(): void {
    this.showViewModal = false;
    this.selectedParticipant = null;
  }

  /**
   * Delete a participant
   */
  async deleteParticipant(id: number): Promise<void> {
    const confirmed = await this.dialog.confirm('Warning', 'Are you sure you want to delete this participant?');
    if (!confirmed) return;

    this.http.delete(`http://localhost:8000/api/participants/${id}`)
      .subscribe({
        next: () => {
          this.dialog.success('Deleted!', 'Participant deleted successfully.');
          this.loadParticipants();
        },
        error: (error) => {
          console.error('Error deleting participant:', error);
          this.dialog.error('Delete failed', error.error?.detail || error.error?.message || 'Could not delete the participant. Please try again.');
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
    localStorage.removeItem('userToken');
    localStorage.removeItem('userRole');
    this.router.navigate(['/login']);
  }

  /**
   * Navigate to dashboard
   */
  goToDashboard(): void {
    this.router.navigate(['/dashboard']);
  }

  /**
   * Navigate to organizer
   */
  goToOrganizer(): void {
    this.router.navigate(['/organizer']);
  }

  /**   
   * Navigate to students
   */
  goToStudents(): void {
    this.router.navigate(['/students']);
  }
}
