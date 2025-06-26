import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
from datetime import datetime
import time
import dateutil.parser

load_dotenv()

class AppointmentDatabase:
    def __init__(self):
        """Initialize database connection"""
        self.connection = None
        self.cursor = None
        self.connect_with_retry()
    
    def connect_with_retry(self, max_retries=3):
        """Connect to database with retry mechanism"""
        retries = 0
        while retries < max_retries:
            try:
                print(f"Attempting database connection (attempt {retries+1}/{max_retries})...")
                self.connection = mysql.connector.connect(
                    host=os.getenv("DB_HOST", "database-1.c27o6uy4uu0g.us-east-1.rds.amazonaws.com"),
                    user=os.getenv("DB_USER", "admin"),
                    password=os.getenv("DB_PASSWORD", "Pratap#20022"),
                    database=os.getenv("DB_NAME", "database-1"),
                    port=int(os.getenv("DB_PORT", "3306"))
                )
                
                if self.connection.is_connected():
                    self.cursor = self.connection.cursor()
                    db_info = self.connection.get_server_info()
                    print(f"Connected to MySQL Server version {db_info}")
                    self._create_tables()
                    print("Database connection established successfully.")
                    return True
            except Error as e:
                retries += 1
                print(f"Error connecting to MySQL (attempt {retries}/{max_retries}): {e}")
                if retries < max_retries:
                    wait_time = 2 * retries  # Exponential backoff
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print("Failed to connect to database after multiple attempts.")
                    self.connection = None
        return False
    
    def _create_tables(self):
        """Create necessary tables if they don't exist"""
        if not self.connection:
            print("Cannot create tables: No database connection")
            return
            
        create_appointments_table = """
        CREATE TABLE IF NOT EXISTS appointments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            person VARCHAR(100) NOT NULL,
            appointment_date DATE NOT NULL,
            appointment_time TIME NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        create_availability_table = """
        CREATE TABLE IF NOT EXISTS availability (
            id INT AUTO_INCREMENT PRIMARY KEY,
            person VARCHAR(100) NOT NULL,
            day_of_week INT NOT NULL,  -- 0 = Monday, 6 = Sunday
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            UNIQUE KEY person_day_time (person, day_of_week, start_time)
        );
        """
        
        try:
            self.cursor.execute(create_appointments_table)
            self.cursor.execute(create_availability_table)
            self.connection.commit()
            print("Database tables created/verified successfully")
        except Error as e:
            print(f"Error creating tables: {e}")
    
    def add_appointment(self, person, date, time, description=""):
        """Add a new appointment to the database"""
        if not self.connection or not self.connection.is_connected():
            print("Database connection lost. Attempting to reconnect...")
            if not self.connect_with_retry():
                print("Failed to reconnect to database")
                return False
        
        # Debug info    
        print(f"DEBUG: Adding appointment for person={person}, date={date}, time={time}")
            
        try:
            # Convert date and time to appropriate format if needed
            if isinstance(date, str):
                try:
                    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                except ValueError:
                    # Try alternative date formats
                    try:
                        date_obj = dateutil.parser.parse(date).date()
                        print(f"Converted date '{date}' to {date_obj} using dateutil")
                    except:
                        print(f"ERROR: Could not parse date string: {date}")
                        return False
            else:
                date_obj = date
                
            if isinstance(time, str):
                try:
                    time_obj = datetime.strptime(time, "%H:%M").time()
                except ValueError:
                    # Try alternative time formats
                    try:
                        if ":" not in time:
                            # Handle formats like "3pm"
                            if "pm" in time.lower():
                                hour = int(''.join(filter(str.isdigit, time)))
                                if hour < 12:
                                    hour += 12
                                time_obj = datetime.strptime(f"{hour}:00", "%H:%M").time()
                            elif "am" in time.lower():
                                hour = int(''.join(filter(str.isdigit, time)))
                                if hour == 12:
                                    hour = 0
                                time_obj = datetime.strptime(f"{hour}:00", "%H:%M").time()
                            else:
                                time_obj = datetime.strptime(f"{time}:00", "%H:%M").time()
                        else:
                            print(f"ERROR: Could not parse time string: {time}")
                            return False
                    except Exception as e:
                        print(f"ERROR: Failed to parse time '{time}': {e}")
                        return False
            else:
                time_obj = time
                
            print(f"DEBUG: Converted to date_obj={date_obj}, time_obj={time_obj}")
                
            # Check if appointment already exists
            check_query = """
            SELECT COUNT(*) FROM appointments 
            WHERE person = %s AND appointment_date = %s AND appointment_time = %s
            """
            self.cursor.execute(check_query, (person, date_obj, time_obj))
            already_exists = self.cursor.fetchone()[0] > 0
            
            if already_exists:
                print(f"Appointment already exists for {person} on {date_obj} at {time_obj}")
                return True  # Consider it a success if it already exists
                
            # Insert the appointment
            query = """
            INSERT INTO appointments (person, appointment_date, appointment_time, description)
            VALUES (%s, %s, %s, %s)
            """
            print(f"DEBUG: Executing insert query with params: {person}, {date_obj}, {time_obj}, {description}")
            self.cursor.execute(query, (person, date_obj, time_obj, description))
            self.connection.commit()
            print(f"DEBUG: Insert query executed, rows affected: {self.cursor.rowcount}")
            
            # Verify the insertion was successful
            verify_query = """
            SELECT COUNT(*) FROM appointments 
            WHERE person = %s AND appointment_date = %s AND appointment_time = %s
            """
            self.cursor.execute(verify_query, (person, date_obj, time_obj))
            count = self.cursor.fetchone()[0]
            insertion_verified = count > 0
            print(f"DEBUG: Verification query returned count: {count}")
            
            if insertion_verified:
                print(f"SUCCESS: Appointment added successfully for {person} on {date_obj} at {time_obj}")
                # Insert into availability table if not already present
                day_of_week = date_obj.weekday()  # 0 = Monday, 6 = Sunday
                
                # First check if this availability entry already exists
                check_avail_query = """
                SELECT COUNT(*) FROM availability 
                WHERE person = %s AND day_of_week = %s AND start_time = %s
                """
                self.cursor.execute(check_avail_query, (person, day_of_week, time_obj))
                avail_exists = self.cursor.fetchone()[0] > 0
                
                if not avail_exists:
                    try:
                        insert_avail_query = """
                        INSERT INTO availability (person, day_of_week, start_time, end_time)
                        VALUES (%s, %s, %s, %s)
                        """
                        self.cursor.execute(insert_avail_query, (person, day_of_week, time_obj, time_obj))
                        self.connection.commit()
                        print(f"Added availability record for {person} on day {day_of_week} at {time_obj}")
                    except Error as e:
                        # If we get a duplicate key error, just ignore it - the appointment was still created
                        if "Duplicate entry" in str(e):
                            print(f"Availability record already exists (duplicate key). Appointment still successful.")
                        else:
                            print(f"WARNING: Failed to add availability record: {e}")
                else:
                    print(f"Availability record already exists for {person} on day {day_of_week} at {time_obj}")
                
                return True
            else:
                print(f"CRITICAL ERROR: Failed to verify appointment insertion for {person}")
                return False
        except Exception as e:
            print(f"ERROR adding appointment: {e}")
            import traceback
            print(traceback.format_exc())
            
            # Try to reconnect if connection was lost
            if "MySQL Connection not available" in str(e):
                print("Connection lost during query. Attempting to reconnect...")
                if self.connect_with_retry():
                    print("Reconnected. Retrying appointment insertion...")
                    # Try one more time
                    try:
                        self.cursor.execute(query, (person, date_obj, time_obj, description))
                        self.connection.commit()
                        
                        # Verify the insertion
                        self.cursor.execute(verify_query, (person, date_obj, time_obj))
                        retry_verified = self.cursor.fetchone()[0] > 0
                        return retry_verified
                    except Exception as e2:
                        print(f"Error on retry: {e2}")
            return False
    
    def check_availability(self, person, date, time):
        """Check if a person is available at the specified date and time"""
        if not self.connection or not self.connection.is_connected():
            print("Database connection lost. Attempting to reconnect...")
            if not self.connect_with_retry():
                print("Failed to reconnect to database")
                return False
            
        try:
            # Convert date and time to appropriate format if needed
            if isinstance(date, str):
                try:
                    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                except ValueError:
                    try:
                        date_obj = dateutil.parser.parse(date).date()
                    except:
                        print(f"ERROR: Could not parse date string: {date}")
                        return False
            else:
                date_obj = date
                
            if isinstance(time, str):
                try:
                    time_obj = datetime.strptime(time, "%H:%M").time()
                except ValueError:
                    try:
                        if ":" not in time:
                            # Handle formats like "3pm"
                            if "pm" in time.lower():
                                hour = int(''.join(filter(str.isdigit, time)))
                                if hour < 12:
                                    hour += 12
                                time_obj = datetime.strptime(f"{hour}:00", "%H:%M").time()
                            elif "am" in time.lower():
                                hour = int(''.join(filter(str.isdigit, time)))
                                if hour == 12:
                                    hour = 0
                                time_obj = datetime.strptime(f"{hour}:00", "%H:%M").time()
                            else:
                                time_obj = datetime.strptime(f"{time}:00", "%H:%M").time()
                        else:
                            print(f"ERROR: Could not parse time string: {time}")
                            return False
                    except Exception as e:
                        print(f"ERROR: Failed to parse time '{time}': {e}")
                        return False
            else:
                time_obj = time
            
            # Check if there's already an appointment at this time
            query = """
            SELECT COUNT(*) FROM appointments 
            WHERE person = %s AND appointment_date = %s AND appointment_time = %s
            """
            self.cursor.execute(query, (person, date_obj, time_obj))
            count = self.cursor.fetchone()[0]
            
            if count > 0:
                print(f"Found existing appointment for {person} at {date_obj} {time_obj} - not available")
                return False  # Not available, already booked
            
            # First check if the person exists in the availability table
            person_check_query = "SELECT COUNT(*) FROM availability WHERE person = %s"
            self.cursor.execute(person_check_query, (person,))
            person_has_availability = self.cursor.fetchone()[0] > 0
            
            if not person_has_availability:
                print(f"Person '{person}' does not exist in availability table. Setting up default availability.")
                # Auto-create default availability for this person
                self.set_default_availability(person)
                person_has_availability = True
                
            # Check if this time falls within the person's availability
            day_of_week = date_obj.weekday()  # 0 = Monday, 6 = Sunday
            
            query = """
            SELECT COUNT(*) FROM availability 
            WHERE person = %s AND day_of_week = %s 
            AND %s BETWEEN start_time AND end_time
            """
            self.cursor.execute(query, (person, day_of_week, time_obj))
            available_count = self.cursor.fetchone()[0]
            
            # The person is available if:
            # 1. There is a specific availability rule that matches (available_count > 0)
            # 2. OR it's a weekday between 9-5 and they have availability records in general
            if available_count > 0:
                print(f"{person} has explicit availability at {time_obj} on weekday {day_of_week}")
                return True
            elif day_of_week < 5 and 9 <= time_obj.hour < 17:  # Weekday between 9 AM and 5 PM
                print(f"Assuming {person} is available at {time_obj} on weekday {day_of_week} (standard business hours)")
                return True
            else:
                print(f"{person} is NOT available at {time_obj} on weekday {day_of_week}")
                return False
            
        except Exception as e:
            print(f"Error checking availability: {e}")
            # Don't default to available if there's an error
            print(f"Defaulting to unavailable due to error.")
            return False
    
    def get_appointments(self, person=None, date=None):
        """Get appointments for a specific person and/or date"""
        if not self.connection or not self.connection.is_connected():
            print("Database connection lost. Attempting to reconnect...")
            if not self.connect_with_retry():
                print("Failed to reconnect to database")
                return []
            
        try:
            conditions = []
            params = []
            
            if person:
                conditions.append("person = %s")
                params.append(person)
                
            if date:
                if isinstance(date, str):
                    try:
                        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                    except ValueError:
                        try:
                            date_obj = dateutil.parser.parse(date).date()
                            print(f"Converted date '{date}' to {date_obj} using dateutil")
                        except Exception as e:
                            print(f"ERROR: Could not parse date string: {date}, {e}")
                            return []
                else:
                    date_obj = date
                conditions.append("appointment_date = %s")
                params.append(date_obj)
                
            query = "SELECT id, person, appointment_date, appointment_time, description FROM appointments"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            print(f"Executing appointments query: {query} with params {params}")
            self.cursor.execute(query, params)
            results = self.cursor.fetchall()
            print(f"Found {len(results)} appointments matching the criteria")
            
            # Log each appointment for debugging
            for appt in results:
                print(f"Appointment: id={appt[0]}, person={appt[1]}, date={appt[2]}, time={appt[3]}, desc={appt[4]}")
                
            return results
        except Error as e:
            print(f"Error getting appointments: {e}")
            import traceback
            print(traceback.format_exc())
            return []
    
    def cancel_appointment(self, person, date, time):
        """Cancel an appointment for a person at the specified date and time"""
        if not self.connection or not self.connection.is_connected():
            print("Database connection lost. Attempting to reconnect...")
            if not self.connect_with_retry():
                print("Failed to reconnect to database")
                return False
        
        try:
            # Convert date and time to appropriate format if needed
            if isinstance(date, str):
                try:
                    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                except ValueError:
                    try:
                        date_obj = dateutil.parser.parse(date).date()
                        print(f"Converted date '{date}' to {date_obj} using dateutil")
                    except:
                        print(f"ERROR: Could not parse date string: {date}")
                        return False
            else:
                date_obj = date
                
            if isinstance(time, str):
                try:
                    time_obj = datetime.strptime(time, "%H:%M").time()
                except ValueError:
                    try:
                        if ":" not in time:
                            # Handle formats like "3pm"
                            if "pm" in time.lower():
                                hour = int(''.join(filter(str.isdigit, time)))
                                if hour < 12:
                                    hour += 12
                                time_obj = datetime.strptime(f"{hour}:00", "%H:%M").time()
                            elif "am" in time.lower():
                                hour = int(''.join(filter(str.isdigit, time)))
                                if hour == 12:
                                    hour = 0
                                time_obj = datetime.strptime(f"{hour}:00", "%H:%M").time()
                            else:
                                time_obj = datetime.strptime(f"{time}:00", "%H:%M").time()
                        else:
                            print(f"ERROR: Could not parse time string: {time}")
                            return False
                    except Exception as e:
                        print(f"ERROR: Failed to parse time '{time}': {e}")
                        return False
            else:
                time_obj = time
            
            # Check if the appointment exists
            check_query = """
            SELECT id FROM appointments 
            WHERE person = %s AND appointment_date = %s AND appointment_time = %s
            """
            self.cursor.execute(check_query, (person, date_obj, time_obj))
            result = self.cursor.fetchone()
            
            if not result:
                print(f"No appointment found for {person} on {date_obj} at {time_obj}")
                return False
                
            # Delete the appointment
            delete_query = """
            DELETE FROM appointments 
            WHERE person = %s AND appointment_date = %s AND appointment_time = %s
            """
            self.cursor.execute(delete_query, (person, date_obj, time_obj))
            self.connection.commit()
            
            if self.cursor.rowcount > 0:
                print(f"Successfully canceled appointment for {person} on {date_obj} at {time_obj}")
                return True
            else:
                print(f"Failed to cancel appointment. No rows affected.")
                return False
                
        except Exception as e:
            print(f"Error canceling appointment: {e}")
            return False
    
    def set_default_availability(self, person, weekday_hours=None):
        """Set default availability for a person (9 AM to 5 PM on weekdays)"""
        if not self.connection:
            return False
            
        if weekday_hours is None:
            # Default to 9 AM - 5 PM on weekdays (Monday=0 to Friday=4)
            weekday_hours = {
                0: [("09:00", "17:00")],  # Monday
                1: [("09:00", "17:00")],  # Tuesday
                2: [("09:00", "17:00")],  # Wednesday
                3: [("09:00", "17:00")],  # Thursday
                4: [("09:00", "17:00")]   # Friday
            }
            
        try:
            # First delete any existing availability for this person
            delete_query = "DELETE FROM availability WHERE person = %s"
            self.cursor.execute(delete_query, (person,))
            
            # Insert new availability
            insert_query = """
            INSERT INTO availability (person, day_of_week, start_time, end_time)
            VALUES (%s, %s, %s, %s)
            """
            
            for day, time_ranges in weekday_hours.items():
                for start_time, end_time in time_ranges:
                    start_time_obj = datetime.strptime(start_time, "%H:%M").time()
                    end_time_obj = datetime.strptime(end_time, "%H:%M").time()
                    self.cursor.execute(insert_query, (person, day, start_time_obj, end_time_obj))
            
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error setting availability: {e}")
            return False
    
    def person_exists_in_availability(self, person):
        """Check if a person exists in the availability table"""
        if not self.connection:
            return False
            
        try:
            query = "SELECT COUNT(*) FROM availability WHERE person = %s"
            self.cursor.execute(query, (person,))
            count = self.cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            print(f"Error checking if person exists in availability: {e}")
            return False
            
    def close(self):
        """Close the database connection"""
        if self.connection:
            self.cursor.close()
            self.connection.close() 