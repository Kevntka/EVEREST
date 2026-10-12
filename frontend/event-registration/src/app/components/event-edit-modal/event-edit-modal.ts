import { ChangeDetectorRef, Component, EventEmitter, Input, OnInit, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { finalize } from 'rxjs';
import { DialogService } from '../../services/dialog.service';
import { shrinkImage } from '../../utils/image-resize';

/**
 * Edit Event modal for the admin Dashboard. Loads the event, then saves it with
 * PUT /api/events/{id} (admins may edit any event). The form and its checks are
 * copied from organizer-events, which keeps its own Create/Edit modal.
 */
@Component({
  selector: 'app-event-edit-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './event-edit-modal.html',
  styleUrl: './event-edit-modal.css'
})
export class EventEditModal implements OnInit {
  @Input({ required: true }) eventId!: number;
  @Output() saved = new EventEmitter<void>();
  @Output() closed = new EventEmitter<void>();

  private http = inject(HttpClient);
  private dialog = inject(DialogService);
  private cdr = inject(ChangeDetectorRef);

  loaded = false;  // the modal shows once the event's current values are in the form
  isSaving = false;
  coverProcessing = false; // shrinking a large photo; Save waits for it

  form = {
    title: '',
    description: '',
    aboutEvent: '',
    date: '',
    time: '',
    endTime: '',
    venue: '',
    capacity: 0,
    registrationStart: '',
    registrationEnd: '',
    department: '',
    coverPhoto: null as File | null
  };

  /** Cover photo types, same as the backend's image check */
  private readonly coverTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
  /** Photos up to 25 MB (e.g. 4K) can be picked; they are shrunk below the backend's 5 MB */
  private readonly coverPickMaxBytes = 25 * 1024 * 1024;
  private readonly coverUploadMaxBytes = 5 * 1024 * 1024;

  ngOnInit(): void {
    this.http.get<any>(`http://localhost:8000/api/events/${this.eventId}`)
      .subscribe({
        next: (response) => {
          const evt = response.event;
          this.form = {
            title: evt.event_name || '',
            description: evt.event_description || '',
            aboutEvent: evt.about_event || '',
            date: evt.event_date || '',
            time: (evt.event_time || '').slice(0, 5),
            endTime: (evt.event_end_time || '').slice(0, 5),
            venue: evt.venue || '',
            capacity: evt.capacity || 0,
            registrationStart: evt.registration_start || '',
            registrationEnd: evt.registration_end || '',
            department: evt.department || '',
            coverPhoto: null
          };
          this.loaded = true;
        },
        error: (error) => {
          console.error('Error loading event:', error);
          this.dialog.error('Something went wrong', error.error?.detail || 'Could not load the event.');
          this.closed.emit();
        }
      });
  }

  async onFileSelected(event: any): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    this.form.coverPhoto = null;
    if (!file) return;

    const reject = (message: string) => {
      this.dialog.error('Check your input', message);
      input.value = '';
    };
    if (!this.coverTypes.includes(file.type)) {
      return reject('Cover photo must be a JPG, PNG, GIF, or WebP image.');
    }
    if (file.size > this.coverPickMaxBytes) {
      return reject('Cover photo must be 25 MB or smaller.');
    }

    this.coverProcessing = true;
    this.cdr.markForCheck();
    try {
      const photo = await shrinkImage(file);
      if (photo.size > this.coverUploadMaxBytes) {
        // Only GIFs aren't shrunk, so only a large GIF ends up here
        reject('This GIF is over 5 MB. Please use a smaller GIF or a JPG/PNG photo.');
      } else {
        this.form.coverPhoto = photo;
      }
    } catch {
      reject('Could not read that image. Please choose another photo.');
    } finally {
      this.coverProcessing = false;
      this.cdr.markForCheck();
    }
  }

  save(): void {
    // Name the empty required fields when there are one or two; otherwise a short general message
    // (About this Event and Cover Photo are optional)
    const { title, description, department, time, endTime, date, capacity, venue, registrationStart, registrationEnd } = this.form;
    const missing = [
      !title.trim() && 'Event Title',
      !description.trim() && 'Description',
      !registrationStart && 'Registration start date',
      !registrationEnd && 'Registration end date',
      !time && 'Start time',
      !endTime && 'End time',
      !date && 'Start Date',
      !capacity && 'Capacity',
      !department.trim() && 'Department',
      !venue.trim() && 'Venue',
    ].filter(Boolean);
    if (missing.length) {
      this.dialog.error('Check your input', missing.length <= 2
        ? `Please fill in the ${missing.join(' and ')}.`
        : 'Please fill in all the empty required fields.');
      return;
    }
    // "HH:MM" strings compare correctly as text
    if (endTime <= time) {
      this.dialog.error('Check your input', 'End time must be after the start time.');
      return;
    }
    if (capacity < 1) {
      this.dialog.error('Check your input', 'Capacity must be at least 1.');
      return;
    }
    // "YYYY-MM-DD" strings compare correctly as text
    if (registrationEnd < registrationStart) {
      this.dialog.error('Check your input', "Registration end can't be before the registration start.");
      return;
    }
    if (date && registrationEnd > date) {
      this.dialog.error('Check your input', 'Registration must end on or before the event date.');
      return;
    }

    const formData = new FormData();
    formData.append('event_name', title);
    formData.append('event_description', description);
    formData.append('event_date', date);
    formData.append('event_time', time);
    formData.append('event_end_time', endTime);
    formData.append('registration_start', registrationStart);
    formData.append('registration_end', registrationEnd);
    formData.append('venue', venue);
    formData.append('department', department);
    formData.append('about_event', this.form.aboutEvent);
    formData.append('capacity', capacity.toString());
    if (this.form.coverPhoto) {
      formData.append('cover_photo', this.form.coverPhoto);
    }

    this.isSaving = true;
    this.http.put<any>(`http://localhost:8000/api/events/${this.eventId}`, formData)
      .pipe(finalize(() => (this.isSaving = false)))
      .subscribe({
        next: () => {
          this.saved.emit();
          this.dialog.success('Success!', 'Event updated successfully!');
        },
        error: (error) => {
          console.error('Error saving event:', error);
          this.dialog.error('Something went wrong', 'Error updating event: ' + (error.error?.detail || 'Please try again.'));
        }
      });
  }
}
