"""
Database Models for EVEREST Event Registration System
Matching the actual PostgreSQL schema
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, SmallInteger, ForeignKey, BigInteger, CheckConstraint, Boolean, Date, Time
from sqlalchemy.sql import func
from database.config import Base


class User(Base):
    """Users table - stores user information and authentication"""
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String(254), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)
    role = Column(String(50), nullable=False)
    is_active = Column(SmallInteger, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class UserRole(Base):
    """User Roles - additional role information"""
    __tablename__ = "user_roles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role_type = Column(String(50), nullable=False)
    department_id = Column(BigInteger, ForeignKey('departments.id'))
    employment_id = Column(String(50), unique=True)
    student_number = Column(String(50))
    contact_number = Column(String(30))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<UserRole(id={self.id}, user_id={self.user_id}, role_type={self.role_type})>"


class Department(Base):
    """Departments table"""
    __tablename__ = "departments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    department_name = Column(String(150), unique=True, nullable=False)

    def __repr__(self):
        return f"<Department(id={self.id}, name={self.department_name})>"


class Event(Base):
    """Events table"""
    __tablename__ = "events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_role_id = Column(BigInteger, ForeignKey('user_roles.id'), nullable=False)
    event_name = Column(String(200), nullable=False)
    event_description = Column(Text)
    event_date = Column(Date)
    event_time = Column(Time)
    venue = Column(String(200))
    capacity = Column(Integer)
    status = Column(String(50), default='open')
    cover_photo = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Event(id={self.id}, event_name={self.event_name})>"


class Registration(Base):
    """Registrations table"""
    __tablename__ = "registrations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(BigInteger, ForeignKey('events.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    registration_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50), default='pending')

    def __repr__(self):
        return f"<Registration(id={self.id}, event_id={self.event_id}, user_id={self.user_id})>"


class Attendee(Base):
    """Attendees table"""
    __tablename__ = "attendees"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    registration_id = Column(BigInteger, ForeignKey('registrations.id', ondelete='CASCADE'), nullable=False)
    department_id = Column(BigInteger, ForeignKey('departments.id'))
    full_name = Column(String(150), nullable=False)
    email = Column(String(254))
    contact_number = Column(String(30))
    student_number = Column(String(50))
    year_level = Column(SmallInteger)
    address = Column(Text)
    gender = Column(String(30))
    profile_picture_url = Column(Text)
    attendance_status = Column(String(20), default='not_recorded')
    attended_at = Column(DateTime(timezone=True))

    def __repr__(self):
        return f"<Attendee(id={self.id}, full_name={self.full_name})>"
