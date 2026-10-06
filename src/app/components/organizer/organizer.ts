import { Component, OnInit, ChangeDetectorRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SelectComponent, SelectOption } from '../select/select';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { LucideAngularModule, LayoutDashboard, Calendar, User, GraduationCap, Users, Menu, Moon, Sun, LogOut, ChevronDown, Search, Edit, Trash2 } from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';
import { DialogService } from '../../services/dialog.service';
import { SessionService } from '../../services/session.service';

import { finalize } from 'rxjs';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';
import { Paginator } from '../../utils/paginator';
import { DisplayCasePipe, displayCase } from '../../utils/display-case.pipe';
export interface Organizer {
  id: number;
  employment_id: string;
  full_name: string;
  department: string;
  email: string;
  contact_number: string;
}

/**
 * Organizer Component
 * Manage event organizers with search and filter capabilities
 */
@Component({
  selector: 'app-organizer',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective, DisplayCasePipe, SelectComponent],
  templateUrl: './organizer.html',
  styleUrl: './organizer.css'
})
export class Organizer implements OnInit {
  readonly pager = new Paginator(10); // 10 rows per page
  isSaving = false; // disables the submit button while the request runs
  private dialog = inject(DialogService);
  private session = inject(SessionService);
  showDropdown = false;
  sidebarOpen = true;
  searchName = '';
  selectedDepartment = '';
  showAddModal = false;
  editingOrganizerId: number | null = null;
  organizers: Organizer[] = [];
  isLoading = true; // Add loading state

  // Unique departments of the loaded organizers, for the filter dropdown
  /** Department filter: "All Departments" plus each department (shown in Title Case). */
  get departmentOptions(): SelectOption[] {
    return [{ value: '', label: 'All Departments' }, ...this.departments.map(d => ({ value: d, label: displayCase(d) }))];
  }

  get departments(): string[] {
    return [...new Set(this.organizers.map(o => o.department).filter(Boolean))].sort();
  }

  // Organizers matching the search box and the department filter
  get filteredOrganizers(): Organizer[] {
    const name = this.searchName.trim().toLowerCase();
    return this.organizers.filter(o =>
      (o.full_name || '').toLowerCase().includes(name) &&
      (this.selectedDepartment === '' || o.department === this.selectedDepartment)
    );
  }

  // Form fields
  newOrganizer = {
    employmentId: '',
    fullName: '',
    department: '',
    email: '',
    contactNumber: ''
  };
  
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
  readonly Edit = Edit;
  readonly Trash2 = Trash2;

  constructor(
    private router: Router, 
    public themeService: ThemeService, 
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    console.log('🚀 Organizer component initialized');
    console.log('⏰ Current organizers array:', this.organizers);
    console.log('📞 Calling loadOrganizers()...');
    
    // Use setTimeout to ensure it runs after component is fully initialized
    setTimeout(() => {
      this.loadOrganizers();
    }, 0);
  }

  /**
   * Load organizers from API
   */
  loadOrganizers(): void {
    console.log('🔍 Loading organizers from API...');
    console.log('🌐 API URL: http://localhost:8000/api/organizers');
    
    this.isLoading = true; // Set loading state
    
    this.http.get<any>('http://localhost:8000/api/organizers', {
      withCredentials: true  // Include cookies for authentication
    })
      .subscribe({
        next: (response) => {
          console.log('✅ Organizers API response:', response);
          console.log('📦 Response type:', typeof response);
          console.log('📦 Response keys:', Object.keys(response));
          
          this.organizers = response.organizers || [];
          this.isLoading = false; // Clear loading state
          
          console.log('📊 Organizers loaded:', this.organizers);
          console.log('📊 Organizers count:', this.organizers.length);
          console.log('📊 Organizers array type:', Array.isArray(this.organizers));
          
          // Force Angular to detect changes
          this.cdr.detectChanges();
        },
        error: (error) => {
          console.error('❌ Error loading organizers:', error);
          console.error('❌ Error status:', error.status);
          console.error('❌ Error message:', error.message);
          console.error('❌ Error details:', error.error);
          
          // Initialize empty array on error
          this.organizers = [];
          this.isLoading = false; // Clear loading state
          
          // Force Angular to detect changes
          this.cdr.detectChanges();
          
          // Don't show alert during debugging
          console.error('🚨 Failed to load organizers - check console for details');
        },
        complete: () => {
          console.log('🏁 HTTP request completed (success or error)');
        }
      });
      
    // Safety timeout - if no response after 10 seconds
    setTimeout(() => {
      if (this.isLoading) {
        console.error('⏰ TIMEOUT: No response from server after 10 seconds');
        this.isLoading = false;
        this.organizers = [];
        this.cdr.detectChanges();
        this.dialog.error('Server Not Responding', 'Please check if the backend is running on http://localhost:8000');
      }
    }, 10000);
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

  /**
   * Close the Edit Organizer modal
   */
  closeAddModal(): void {
    this.showAddModal = false;
    this.editingOrganizerId = null;
    this.resetForm();
  }

  /**
   * Open the organizer form pre-filled for editing
   */
  openEditModal(organizer: any): void {
    this.newOrganizer = {
      employmentId: organizer.employment_id || '',
      fullName: organizer.full_name || '',
      department: organizer.department === 'N/A' ? '' : (organizer.department || ''),
      email: organizer.email || '',
      contactNumber: organizer.contact_number === 'N/A' ? '' : (organizer.contact_number || '')
    };
    this.editingOrganizerId = organizer.id;
    this.showAddModal = true;
  }

  /**
   * Reset form fields
   */
  resetForm(): void {
    this.newOrganizer = {
      employmentId: '',
      fullName: '',
      department: '',
      email: '',
      contactNumber: ''
    };
  }

  /**
   * Input validation handlers
   */
  
  // Full Name - Letters and spaces only, auto uppercase
  onFullNameInput(event: any): void {
    let value = event.target.value;
    // Remove non-letter characters (except spaces)
    value = value.replace(/[^A-Za-z\s]/g, '');
    // Convert to uppercase
    value = value.toUpperCase();
    this.newOrganizer.fullName = value;
    event.target.value = value;
  }

  // Employment ID - Numbers only, auto uppercase
  onEmploymentIdInput(event: any): void {
    let value = event.target.value;
    // Remove non-numeric characters
    value = value.replace(/[^0-9]/g, '');
    // Convert to uppercase (for display consistency)
    value = value.toUpperCase();
    this.newOrganizer.employmentId = value;
    event.target.value = value;
  }

  // Department - Letters and spaces only, auto uppercase
  onDepartmentInput(event: any): void {
    let value = event.target.value;
    // Remove non-letter characters (except spaces)
    value = value.replace(/[^A-Za-z\s]/g, '');
    // Convert to uppercase
    value = value.toUpperCase();
    this.newOrganizer.department = value;
    event.target.value = value;
  }

  // Email - Lowercase only, valid format
  onEmailInput(event: any): void {
    let value = event.target.value;
    // Convert to lowercase for email
    value = value.toLowerCase();
    this.newOrganizer.email = value;
    event.target.value = value;
  }

  // Contact Number - Numbers only, auto-format (0912-345-6789)
  onContactNumberInput(event: any): void {
    let value = event.target.value;
    // Remove all non-numeric characters
    const numbersOnly = value.replace(/[^0-9]/g, '');
    
    // Format: 0912-345-6789
    let formatted = '';
    if (numbersOnly.length > 0) {
      formatted = numbersOnly.substring(0, 4); // First 4 digits
      if (numbersOnly.length > 4) {
        formatted += '-' + numbersOnly.substring(4, 7); // Next 3 digits
      }
      if (numbersOnly.length > 7) {
        formatted += '-' + numbersOnly.substring(7, 11); // Last 4 digits
      }
    }
    
    this.newOrganizer.contactNumber = formatted;
    event.target.value = formatted;
  }

  /**
   * Save the Edit Organizer form (organizers register themselves; admins only edit them)
   */
  saveOrganizer(): void {
    if (this.editingOrganizerId === null) return;

    // Validate only REQUIRED fields (contactNumber is optional)
    if (!this.newOrganizer.employmentId || !this.newOrganizer.fullName ||
        !this.newOrganizer.department || !this.newOrganizer.email) {
      this.dialog.error('Check your input', 'Please fill in all required fields');
      return;
    }

    const formData = new FormData();
    formData.append('employment_id', this.newOrganizer.employmentId);
    formData.append('full_name', this.newOrganizer.fullName);
    formData.append('department', this.newOrganizer.department);
    formData.append('email', this.newOrganizer.email);
    formData.append('contact_number', this.newOrganizer.contactNumber);

    // Saved now: closeAddModal() clears the form before the message below is shown
    const name = displayCase(this.newOrganizer.fullName.trim());

    this.isSaving = true;
    this.http.put<any>(`http://localhost:8000/api/organizers/${this.editingOrganizerId}`, formData)
      .pipe(finalize(() => (this.isSaving = false)))
      .subscribe({
        next: () => {
          this.closeAddModal();
          this.loadOrganizers();
          this.dialog.success('Success!', `Your changes to ${name} have been saved.`);
        },
        error: (error) => {
          console.error('Error updating organizer:', error);
          this.dialog.error('Could Not Update Organizer', error.error?.detail || 'Please try again.');
        }
      });
  }

  /**
   * Delete organizer
   */
  async deleteOrganizer(id: number): Promise<void> {
    const confirmed = await this.dialog.confirm('Warning', 'Are you sure you want to delete this organizer?');
    if (!confirmed) return;

    this.http.delete(`http://localhost:8000/api/organizers/${id}`)
      .subscribe({
        next: () => {
          this.dialog.success('Deleted!', 'The organizer has been deleted, along with their events.');
          this.loadOrganizers();
        },
        error: (error) => {
          console.error('Error deleting organizer:', error);
          this.dialog.error('Delete failed', error.error?.detail || error.error?.message || 'Could not delete the organizer. Please try again.');
        }
      });
  }
}
