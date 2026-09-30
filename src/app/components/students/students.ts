import { Component, OnInit, ChangeDetectorRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { LucideAngularModule, LayoutDashboard, Calendar, User, GraduationCap, Users, Menu, Moon, Sun, LogOut, ChevronDown, Search, Eye, Trash2, Mail, Building2, Phone, UserRound } from 'lucide-angular';
import { ThemeService } from '../../services/theme.service';
import { DialogService } from '../../services/dialog.service';

import { ClickOutsideDirective } from '../../directives/click-outside.directive';
import { Paginator } from '../../utils/paginator';
export interface Student {
  id: number;
  full_name: string;
  email: string;
  department: string;
  year_level: string;
  gender: string;
  contact_number: string;
}

/**
 * Students Component
 * Manage students with search and filter capabilities
 */
@Component({
  selector: 'app-students',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ClickOutsideDirective],
  templateUrl: './students.html',
  styleUrl: './students.css'
})
export class Students implements OnInit {
  readonly pager = new Paginator(10); // 10 rows per page
  private dialog = inject(DialogService);
  showDropdown = false;
  sidebarOpen = true;
  searchName = '';
  selectedDepartment = '';
  students: Student[] = [];
  filteredStudents: Student[] = [];
  showViewModal = false;
  selectedStudent: Student | null = null;
  
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
  readonly Building2 = Building2;
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
          this.filteredStudents = this.students;
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
      const matchesName = student.full_name.toLowerCase().includes(this.searchName.toLowerCase());
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
   * Navigate to participants page
   */
  goToParticipants(): void {
    this.router.navigate(['/participants']);
  }
}
