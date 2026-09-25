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
