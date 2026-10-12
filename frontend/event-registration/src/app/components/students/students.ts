import { Component, OnInit, ChangeDetectorRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SelectComponent, SelectOption } from '../select/select';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { LucideAngularModule, LayoutDashboard, Calendar, User, GraduationCap, Users, Menu, Moon, Sun, LogOut, ChevronDown, Search, Eye, Edit, Trash2, Mail, Building2, Phone, UserRound, IdCard, BookOpen } from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';
import { DialogService } from '../../services/dialog.service';
import { SessionService } from '../../services/session.service';

import { finalize } from 'rxjs';
import { ClickOutsideDirective } from '../../directives/click-outside.directive';
import { Paginator } from '../../utils/paginator';
import { matchesSearch } from '../../utils/search';
import { DisplayCasePipe, displayCase } from '../../utils/display-case.pipe';
export interface Student {
  id: number;
  full_name: string;
  email: string;
  sr_code: string;
  department: string;
  program: string;
  year_level: string;
  gender: string;
  contact_number: string;
  avatar_url?: string;  // '/api/users/{id}/avatar', or '' without a picture
}

/** 'N/A' (the list's placeholder for an empty field) -> '' for the Edit form. */
function formValue(value: string | null | undefined): string {
  return value && value !== 'N/A' ? value : '';
}

/**
 * Students Component
 * Manage students with search and filter capabilities
 */
@Component({
  selector: 'app-students',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective, DisplayCasePipe, SelectComponent],
  templateUrl: './students.html',
  styleUrls: ['./students.css', '../admin-table.css']
})
export class Students implements OnInit {
  readonly pager = new Paginator(10); // 10 rows per page
  private dialog = inject(DialogService);
  private session = inject(SessionService);
  showDropdown = false;
  sidebarOpen = true;
  searchName = '';
  selectedDepartment = '';
  students: Student[] = [];
  filteredStudents: Student[] = [];

  // Unique departments of the loaded students, for the filter dropdown
  /** Department filter: "All Departments" plus each department (shown in Title Case). */
  get departmentOptions(): SelectOption[] {
    return [{ value: '', label: 'All Departments' }, ...this.departments.map(d => ({ value: d, label: displayCase(d) }))];
  }

  get departments(): string[] {
    return [...new Set(this.students.map(s => s.department).filter(Boolean))].sort();
  }
  showViewModal = false;
  selectedStudent: Student | null = null;
  
  // Lucide icons
  readonly LayoutDashboard = LayoutDashboard;
  readonly Calendar = Calendar;
  readonly User = User;
  readonly GraduationCap = GraduationCap;
  readonly IdCard = IdCard;
  readonly BookOpen = BookOpen;
  readonly Users = Users;
  readonly Menu = Menu;
  readonly Moon = Moon;
  readonly Sun = Sun;
  readonly LogOut = LogOut;
  readonly ChevronDown = ChevronDown;
  readonly Search = Search;
  readonly Eye = Eye;
  readonly Mail = Mail;
  readonly Building2 = Building2;
  readonly Phone = Phone;
  readonly UserRound = UserRound;
  readonly Trash2 = Trash2;
  readonly Edit = Edit;

  // Edit modal (admin): same fields and checks as the student's own Profile page
  readonly yearLevelOptions: SelectOption[] = ['1ST YEAR', '2ND YEAR', '3RD YEAR', '4TH YEAR'].map(l => ({ value: l, label: l }));
  readonly genderOptions: SelectOption[] = [{ value: 'MALE', label: 'MALE' }, { value: 'FEMALE', label: 'FEMALE' }];
  editingStudentId: number | null = null;
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
      this.loadStudents();
    }, 0);
  }

  /**
   * Load students from API
   */
  loadStudents(): void {
    console.log('🔍 Loading students from API...');
    this.http.get<any>('http://localhost:8000/api/students', {
      withCredentials: true
    })
      .subscribe({
        next: (response) => {
          console.log('✅ Students API response:', response);
          this.students = response.students || [];
          this.filterStudents();
          console.log('📊 Students loaded:', this.students);
          console.log('📊 Filtered students:', this.filteredStudents);
          
          // Force Angular to detect changes
          this.cdr.detectChanges();
        },
        error: (error) => {
          console.error('❌ Error loading students:', error);
          this.students = [];
          this.filteredStudents = [];
          this.cdr.detectChanges();
          this.dialog.error('Something went wrong', 'Error loading students: ' + (error.message || 'Unknown error'));
        }
      });
  }

  /**
   * Filter students by search name and department
   */
  filterStudents(): void {
    this.filteredStudents = this.students.filter(student => {
      const matchesName = matchesSearch(student.full_name, this.searchName);
      const matchesDept = this.selectedDepartment === '' || student.department === this.selectedDepartment;
      return matchesName && matchesDept;
    });
  }

  /**
   * View student details
   */
  viewStudent(student: Student): void {
    this.selectedStudent = student;
    this.showViewModal = true;
  }

  /**
   * Close view modal
   */
  closeViewModal(): void {
    this.showViewModal = false;
    this.selectedStudent = null;
  }

  private emptyEditForm() {
    return { fullName: '', email: '', srCode: '', department: '', program: '', yearLevel: '', gender: '', contactNumber: '' };
  }

  /**
   * Open the Edit modal with the student's current details
   */
  openEditModal(student: Student): void {
    this.editForm = {
      fullName: student.full_name,
      email: student.email,
      srCode: formValue(student.sr_code),
      department: formValue(student.department),
      program: formValue(student.program),
      yearLevel: formValue(student.year_level).toUpperCase(),
      gender: formValue(student.gender).toUpperCase(),
      contactNumber: formValue(student.contact_number)
    };
    this.editingStudentId = student.id;
  }

  closeEditModal(): void {
    this.editingStudentId = null;
    this.editForm = this.emptyEditForm();
  }

  /**
   * Save the Edit modal (PUT /api/students/{id})
   */
  saveStudent(): void {
    const f = this.editForm;
    if (!f.fullName.trim() || !f.email.trim()) {
      this.dialog.error('Check your input', 'Please fill in the Full Name and Email.');
      return;
    }
    if (f.srCode.trim() && !/^\d{2}-\d{5}$/.test(f.srCode.trim())) {
      this.dialog.error('Check your input', 'SR Code must look like 23-30046.');
      return;
    }
    if (f.contactNumber.trim() && f.contactNumber.replace(/\D/g, '').length !== 11) {
      this.dialog.error('Check your input', 'Contact number must have 11 digits (0912-345-6789).');
      return;
    }

    const body = {
      fullName: f.fullName.trim(),
      email: f.email.trim(),
      srCode: f.srCode.trim(),
      collegeDepartment: f.department.trim(),
      program: f.program.trim(),
      yearLevel: f.yearLevel,
      gender: f.gender,
      contactNumber: f.contactNumber.trim()
    };
    this.isSaving = true;
    this.http.put<any>(`http://localhost:8000/api/students/${this.editingStudentId}`, body)
      .pipe(finalize(() => (this.isSaving = false)))
      .subscribe({
        next: () => {
          this.closeEditModal();
          this.loadStudents();
          this.dialog.success('Success!', 'Student updated successfully!');
        },
        error: (error) => {
          console.error('Error updating student:', error);
          this.dialog.error('Something went wrong', 'Error updating student: ' + (error.error?.detail || 'Please try again.'));
        }
      });
  }

  /**
   * Delete a student
   */
  async deleteStudent(id: number): Promise<void> {
    const confirmed = await this.dialog.confirm('Warning', 'Are you sure you want to delete this student?');
    if (!confirmed) return;

    this.http.delete(`http://localhost:8000/api/students/${id}`)
      .subscribe({
        next: () => {
          this.dialog.success('Deleted!', 'Student deleted successfully.');
          this.loadStudents();
        },
        error: (error) => {
          console.error('Error deleting student:', error);
          this.dialog.error('Delete failed', error.error?.detail || error.error?.message || 'Could not delete the student. Please try again.');
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
   * Navigate to participants page
   */
  goToParticipants(): void {
    this.router.navigate(['/participants']);
  }
}
