-- Add missing columns to events table if they don't exist

-- Add event_time column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='events' AND column_name='event_time') THEN
        ALTER TABLE events ADD COLUMN event_time TIME;
    END IF;
END $$;

-- Add cover_photo column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='events' AND column_name='cover_photo') THEN
        ALTER TABLE events ADD COLUMN cover_photo TEXT;
    END IF;
END $$;

-- Add department and about_event columns (shown on the event details page)
ALTER TABLE events ADD COLUMN IF NOT EXISTS department VARCHAR(150);
ALTER TABLE events ADD COLUMN IF NOT EXISTS about_event TEXT;

-- Cover photo image bytes live in the database (served by GET /api/events/{id}/cover)
ALTER TABLE events ADD COLUMN IF NOT EXISTS cover_photo_data BYTEA;
ALTER TABLE events ADD COLUMN IF NOT EXISTS cover_photo_type VARCHAR(100);

-- Student/participant profile fields (edited on the Profile page)
-- Event end time (events auto-close once it passes)
ALTER TABLE events ADD COLUMN IF NOT EXISTS event_end_time TIME;

-- Enrolling opens on this date (NULL: on the event date)
ALTER TABLE events ADD COLUMN IF NOT EXISTS registration_start DATE;
-- Last day to enroll (NULL: until the event ends)
ALTER TABLE events ADD COLUMN IF NOT EXISTS registration_end DATE;

-- (profile fields)
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS gender VARCHAR(30);
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS year_level VARCHAR(20);
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS program VARCHAR(150);
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS address VARCHAR(255);
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS birthday DATE;

-- Profile picture bytes (served by GET /api/users/{id}/avatar)
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS avatar_data BYTEA;
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS avatar_type VARCHAR(100);

-- Student/participant sign-ups waiting for their 6-digit email code (SHA-256 hash only).
-- The real account is created in users only after the code is verified.
CREATE TABLE IF NOT EXISTS pending_registrations (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(254) UNIQUE NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    role VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    department VARCHAR(150),
    contact_number VARCHAR(30),
    code_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    attempts SMALLINT NOT NULL DEFAULT 0,
    last_sent_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
DROP TABLE IF EXISTS email_verification_codes;

-- Rename columns if they have different names
DO $$ 
BEGIN
    -- Check if event_name exists, if not rename title to event_name
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='events' AND column_name='event_name') THEN
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='events' AND column_name='title') THEN
            ALTER TABLE events RENAME COLUMN title TO event_name;
        END IF;
    END IF;
END $$;

SELECT 'Event table columns updated successfully!' as message;
