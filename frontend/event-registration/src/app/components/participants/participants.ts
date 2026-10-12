import { Component, OnInit, ChangeDetectorRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SelectComponent, SelectOption } from '../select/select';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { LucideAngularModule, LayoutDashboard, Calendar, User, GraduationCap, Users, Menu, Moon, Sun, LogOut, ChevronDown, Search, Eye, Edit, Trash2, Mail, MapPin, Phone, UserRound, Cake, Hourglass } from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';
import { DialogService } from '../../services/dialog.service';
import { SessionService } from '../../services/session.service';

import { finalize } from 'rxjs';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';
import { Paginator } from '../../utils/paginator';
import { matchesSearch } from '../../utils/search';
import { DisplayCasePipe } from '../../utils/display-case.pipe';
export interface Participant {
  id: number;
  full_name: string;
  email: string;
  address: string;
  birthday: string; // YYYY-MM-DD or 'N/A'
  age: string;      // from the birthday, or 'N/A'
  gender: string;
  contact_number: string;
  avatar_url?: string;  // '/api/users/{id}/avatar', or '' without a picture
}

/** 'N/A' (the list's placeholder for an empty field) -> '' for the Edit form. */
function formValue(value: string | null | undefined): string {
  return value && value !== 'N/A' ? value : '';
}

/**
 * Participants Component
 * Manage participants with search and filter capabilities
 */
@Component({
  selector: 'app-participants',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective, DisplayCasePipe, SelectComponent],
  templateUrl: './participants.html',
  styleUrls: ['./participants.css', '../admin-table.css']
})
export class Participants implements OnInit {
  readonly pager = new Paginator(10); // 10 rows per page
  private dialog = inject(DialogService);
  private session = inject(SessionService);
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
  readonly Cake = Cake;
  readonly Hourglass = Hourglass;
  readonly Phone = Phone;
  readonly UserRound = UserRound;
  readonly Trash2 = Trash2;
  readonly Edit = Edit;

  // Edit modal (admin): same fields and checks as the participant's own Profile page
  readonly genderOptions: SelectOption[] = [{ value: 'MALE', label: 'MALE' }, { value: 'FEMALE', label: 'FEMALE' }];
  /** Birthday picker can't go past today. */
  readonly today = new Date().toLocaleDateString('en-CA');
  editingParticipantId: number | null = null;
  isSaving = false;
  editForm = this.emptyEditForm();

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
      return matchesSearch(participant.full_name, this.searchName);
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

  private emptyEditForm() {
    return { fullName: '', email: '', address: '', birthday: '', gender: '', contactNumber: '' };
  }

  /**
   * Open the Edit modal with the participant's current details
   */
  openEditModal(participant: Participant): void {
    this.editForm = {
      fullName: participant.full_name,
      email: participant.email,
      address: formValue(participant.address),
      birthday: formValue(participant.birthday),
      gender: formValue(participant.gender).toUpperCase(),
      contactNumber: formValue(participant.contact_number)
    };
    this.editingParticipantId = participant.id;
  }

  closeEditModal(): void {
    this.editingParticipantId = null;
    this.editForm = this.emptyEditForm();
  }

  /**
   * Save the Edit modal (PUT /api/participants/{id})
   */
  saveParticipant(): void {
    const f = this.editForm;
    if (!f.fullName.trim() || !f.email.trim()) {
      this.dialog.error('Check your input', 'Please fill in the Full Name and Email.');
      return;
    }
    // "YYYY-MM-DD" strings compare correctly as text
    if (f.birthday && f.birthday > this.today) {
      this.dialog.error('Check your input', "Birthday can't be in the future.");
      return;
    }
    if (f.contactNumber.trim() && f.contactNumber.replace(/\D/g, '').length !== 11) {
      this.dialog.error('Check your input', 'Contact number must have 11 digits (0912-345-6789).');
      return;
    }

    const body = {
      fullName: f.fullName.trim(),
      email: f.email.trim(),
      address: f.address.trim(),
      birthday: f.birthday,
      gender: f.gender,
      contactNumber: f.contactNumber.trim()
    };
    this.isSaving = true;
    this.http.put<any>(`http://localhost:8000/api/participants/${this.editingParticipantId}`, body)
      .pipe(finalize(() => (this.isSaving = false)))
      .subscribe({
        next: () => {
          this.closeEditModal();
          this.loadParticipants();
          this.dialog.success('Success!', 'Participant updated successfully!');
        },
        error: (error) => {
          console.error('Error updating participant:', error);
          this.dialog.error('Something went wrong', 'Error updating participant: ' + (error.error?.detail || 'Please try again.'));
        }
      });
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
    this.session.signOut();
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
