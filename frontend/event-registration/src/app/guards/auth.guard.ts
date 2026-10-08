import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { CanActivateFn } from '@angular/router';

export const authGuard: CanActivateFn = (route, state) => {
  const router = inject(Router);

  // The backend keeps the access token in an HTTP-only cookie, so it is not
  // available through localStorage. The API remains the source of truth.
  const userRole = localStorage.getItem('userRole');

  if (userRole) {
    return true;
  }
  
  // User is not authenticated, redirect to login
  console.log('Access denied. Redirecting to login...');
  router.navigate(['/login']);
  return false;
};

/**
 * Login Guard - Prevents logged-in users from accessing login page
 * Redirects to appropriate dashboard based on role
 */
export const loginGuard: CanActivateFn = (route, state) => {
  const router = inject(Router);
  
  const userRole = localStorage.getItem('userRole');
  
  if (userRole) {
    // User is already logged in, redirect to their dashboard
    console.log('User already logged in. Redirecting to dashboard...');
    
    switch(userRole) {
      case 'admin':
        router.navigate(['/dashboard']);
        return false;
      case 'organizer':
        router.navigate(['/organizer-dashboard']);
        return false;
      case 'student':
        router.navigate(['/student-dashboard']);
        return false;
      case 'participant':
        router.navigate(['/student-dashboard']);
        return false;
      default:
        router.navigate(['/dashboard']);
        return false;
    }
  }
  
  // User is not logged in, allow access to login page
  return true;
};

export const roleGuard = (allowedRole: string | string[]): CanActivateFn => {
  return (route, state) => {
    const router = inject(Router);
    
    const userRole = localStorage.getItem('userRole');
    
    if (!userRole) {
      // Not logged in, redirect to login
      console.log('No authenticated role found. Redirecting to login...');
      router.navigate(['/login']);
      return false;
    }
    
    if (Array.isArray(allowedRole) ? allowedRole.includes(userRole) : userRole === allowedRole) {
      // User has correct role
      return true;
    }
    
    // User doesn't have correct role, redirect to their own dashboard
    console.log(`Access denied. Required role: ${allowedRole}, User role: ${userRole}`);
    console.log('Redirecting to appropriate dashboard...');
    
    switch(userRole) {
      case 'admin':
        router.navigate(['/dashboard']);
        break;
      case 'organizer':
        router.navigate(['/organizer-dashboard']);
        break;
      case 'student':
        router.navigate(['/student-dashboard']);
        break;
      case 'participant':
        router.navigate(['/student-dashboard']);
        break;
      default:
        router.navigate(['/login']);
        break;
    }
    
    return false;
  };
};
