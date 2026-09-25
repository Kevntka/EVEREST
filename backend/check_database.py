"""
Simple database checker - view all saved data
"""

from database.config import get_db
from models.user import User, UserRole, Department, Event, Registration
from sqlalchemy import text

def main():
    print("\n" + "="*80)
    print(" EVEREST DATABASE - SAVED DATA ".center(80, "="))
    print("="*80 + "\n")
    
    db = next(get_db())
    
    # View Users
    print("👤 USERS:")
    print("-" * 80)
    users = db.query(User).all()
    if users:
        print(f"{'ID':<5} {'Name':<25} {'Email':<35} {'Role':<15}")
        print("-" * 80)
        for user in users:
            print(f"{user.id:<5} {user.full_name:<25} {user.email:<35} {user.role:<15}")
    else:
        print("No users found")
    print(f"\nTotal: {len(users)} users\n")
    
    # View Departments
    print("\n🏢 DEPARTMENTS:")
    print("-" * 80)
    depts = db.query(Department).all()
    if depts:
        for dept in depts:
            print(f"ID {dept.id}: {dept.department_name}")
    else:
        print("No departments found")
    print(f"\nTotal: {len(depts)} departments\n")
    
    # View Events
    print("\n📅 EVENTS:")
    print("-" * 80)
    events = db.query(Event).all()
    if events:
        print(f"{'ID':<5} {'Event Name':<30} {'Date':<15} {'Venue':<20} {'Status':<10}")
        print("-" * 80)
        for event in events:
            print(f"{event.id:<5} {event.event_name:<30} {str(event.event_date):<15} {event.venue:<20} {event.status:<10}")
    else:
        print("No events found")
    print(f"\nTotal: {len(events)} events\n")
    
    # View Registrations
    print("\n📝 REGISTRATIONS:")
    print("-" * 80)
    registrations = db.query(Registration).all()
    if registrations:
        print(f"{'ID':<5} {'Event ID':<10} {'User ID':<10} {'Status':<15}")
        print("-" * 80)
        for reg in registrations:
            print(f"{reg.id:<5} {reg.event_id:<10} {reg.user_id:<10} {reg.status:<15}")
    else:
        print("No registrations found")
    print(f"\nTotal: {len(registrations)} registrations\n")
    
    # Count by role
    print("\n📊 USERS BY ROLE:")
    print("-" * 80)
    role_counts = db.execute(text("""
        SELECT role, COUNT(*) 
        FROM users 
        GROUP BY role 
        ORDER BY role
    """)).fetchall()
    
    for role, count in role_counts:
        print(f"{role.capitalize()}: {count}")
    
    print("\n" + "="*80)
    print("Done!")
    print("="*80 + "\n")
    
    db.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
