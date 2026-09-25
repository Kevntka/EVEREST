-- EVEREST
-- PostgreSQL Database


DROP TABLE IF EXISTS attendees CASCADE;
DROP TABLE IF EXISTS registrations CASCADE;
DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS user_roles CASCADE;
DROP TABLE IF EXISTS departments CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Create departments table
CREATE TABLE departments (
    id BIGSERIAL PRIMARY KEY,
    department_name VARCHAR(150) UNIQUE NOT NULL
);

-- Create users table (for authentication)
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(254) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'organizer', 'student', 'participant')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create user_roles table (for additional role info like organizers)
CREATE TABLE user_roles (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_type VARCHAR(50) NOT NULL,
    department_id BIGINT REFERENCES departments(id),
    employment_id VARCHAR(50) UNIQUE,
    student_number VARCHAR(50),
    contact_number VARCHAR(30),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create events table
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    user_role_id BIGINT NOT NULL REFERENCES user_roles(id),
    event_name VARCHAR(200) NOT NULL,
    event_description TEXT,
    event_date DATE,
    event_time TIME,
    venue VARCHAR(200),
    capacity INTEGER,
    status VARCHAR(50) DEFAULT 'open' CHECK (status IN ('open', 'closed', 'cancelled')),
    cover_photo TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create registrations table
CREATE TABLE registrations (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id),
    registration_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'cancelled')),
    UNIQUE(event_id, user_id)
);

-- Create attendees table (for event attendance)
CREATE TABLE attendees (
    id BIGSERIAL PRIMARY KEY,
    registration_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
    department_id BIGINT REFERENCES departments(id) ON DELETE RESTRICT,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(254),
    contact_number VARCHAR(30),
    student_number VARCHAR(50),
    year_level SMALLINT,
    address TEXT,
    gender VARCHAR(30),
    profile_picture_url TEXT,
    attendance_status VARCHAR(20) DEFAULT 'not_recorded' CHECK (attendance_status IN ('present', 'absent', 'not_recorded')),
    attended_at TIMESTAMP WITH TIME ZONE
);

-- Create password reset tokens table
CREATE TABLE password_reset_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    used BOOLEAN DEFAULT FALSE
);

-- Create indexes for better performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX idx_events_user_role_id ON events(user_role_id);
CREATE INDEX idx_events_status ON events(status);
CREATE INDEX idx_registrations_event_id ON registrations(event_id);
CREATE INDEX idx_registrations_user_id ON registrations(user_id);
CREATE INDEX idx_attendees_registration ON attendees(registration_id);
CREATE INDEX idx_attendees_department ON attendees(department_id);

-- Insert default admin user
INSERT INTO users (email, password, full_name, role, is_active) 
VALUES ('admin@everest.com', 'admin123', 'Administrator', 'admin', TRUE);

-- Insert sample departments
INSERT INTO departments (department_name) VALUES
    ('Computer Science'),
    ('Information Technology'),
    ('Engineering'),
    ('Business Administration'),
    ('Arts and Sciences'),
    ('Education');

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for auto-updating updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_events_updated_at BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_app_user;
