import { Routes } from '@angular/router';
import { Login } from './components/login/login';
import { Register } from './components/register/register';
import { RegisterStudent } from './components/register-student/register-student';
import { RegisterParticipant } from './components/register-participant/register-participant';
import { ForgotPassword } from './components/forgot-password/forgot-password';
import { CheckEmail } from './components/check-email/check-email';

export const routes: Routes = [
  { path: '', redirectTo: '/login', pathMatch: 'full' },
  { path: 'login', component: Login },
  { path: 'register', component: Register },
  { path: 'register/student', component: RegisterStudent },
  { path: 'register/participant', component: RegisterParticipant },
  { path: 'forgot-password', component: ForgotPassword },
  { path: 'check-email', component: CheckEmail },
];
