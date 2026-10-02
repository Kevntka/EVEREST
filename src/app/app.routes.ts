import { Routes } from '@angular/router';
import { Login } from './components/login/login';
import { Register } from './components/register/register';
import { RegisterStudent } from './components/register-student/register-student';
import { RegisterParticipant } from './components/register-participant/register-participant';
import { ForgotPassword } from './components/forgot-password/forgot-password';
import { CheckEmail } from './components/check-email/check-email';
import { VerifyEmail } from './components/verify-email/verify-email';
import { ResetPassword } from './components/reset-password/reset-password';
import { Dashboard } from './components/dashboard/dashboard';
import { Organizer } from './components/organizer/organizer';
import { OrganizerDashboard } from './components/organizer-dashboard/organizer-dashboard';
import { OrganizerEvents } from './components/organizer-events/organizer-events';
import { OrganizerAttendance } from './components/organizer-attendance/organizer-attendance';
import { Students } from './components/students/students';
import { Participants } from './components/participants/participants';
import { StudentDashboard } from './components/student-dashboard/student-dashboard';
import { StudentProfile } from './components/student-profile/student-profile';
import { MyEvents } from './components/my-events/my-events';
import { EventDetails } from './components/event-details/event-details';
import { authGuard, roleGuard, loginGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: '', redirectTo: '/login', pathMatch: 'full' },
  { path: 'login', component: Login, canActivate: [loginGuard] },
  { path: 'register', component: Register, canActivate: [loginGuard] },
  { path: 'register/student', component: RegisterStudent, canActivate: [loginGuard] },
  { path: 'register/participant', component: RegisterParticipant, canActivate: [loginGuard] },
  { path: 'forgot-password', component: ForgotPassword, canActivate: [loginGuard] },
  { path: 'check-email', component: CheckEmail, canActivate: [loginGuard] },
  { path: 'verify-email', component: VerifyEmail, canActivate: [loginGuard] },
  { path: 'reset-password', component: ResetPassword },
  
  // Admin routes (protected)
  { path: 'dashboard', component: Dashboard, canActivate: [roleGuard('admin')] },
  { path: 'organizer', component: Organizer, canActivate: [roleGuard('admin')] },
  { path: 'students', component: Students, canActivate: [roleGuard('admin')] },
  { path: 'participants', component: Participants, canActivate: [roleGuard('admin')] },
  
  // Organizer routes (protected)
  { path: 'organizer-dashboard', component: OrganizerDashboard, canActivate: [roleGuard('organizer')] },
  { path: 'organizer-events', component: OrganizerEvents, canActivate: [roleGuard('organizer')] },
  { path: 'organizer-attendance', component: OrganizerAttendance, canActivate: [roleGuard('organizer')] },
  
  // Student routes (protected)
  { path: 'student-dashboard', component: StudentDashboard, canActivate: [roleGuard(['student', 'participant'])] },
  { path: 'student-profile', component: StudentProfile, canActivate: [roleGuard(['student', 'participant'])] },
  { path: 'my-events', component: MyEvents, canActivate: [roleGuard(['student', 'participant'])] },
  { path: 'event/:id', component: EventDetails, canActivate: [authGuard] },
];
