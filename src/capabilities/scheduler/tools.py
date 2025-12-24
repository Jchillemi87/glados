# src/capabilities/scheduler/tools.py
from datetime import date, timedelta, datetime
from typing import Optional
from langchain_core.tools import tool
from sqlalchemy import text
from src.core.database import get_db_session, MaintenanceLog
from src.core.iot import ha_client

# region CALENDAR (Home Assistant)
@tool
def get_calendar_events(days: int = 1) -> str:
    """
    Fetches calendar events from Home Assistant.
    Args:
        days: How many days of events to fetch (default 1 for 'Today').
    """
    # Calculate Time Window
    now = datetime.now()
    end = now + timedelta(days=days)
    
    # ISO Format required by HA API: "2025-01-01T00:00:00"
    start_str = now.strftime("%Y-%m-%dT00:00:00")
    end_str = end.strftime("%Y-%m-%dT23:59:59")
    
    # Call Home Assistant API (Using generic GET /api/calendars)
    # Note: We need to loop through available calendars or query a specific one.
    # We will try to fetch ALL calendars.
    try:
        # Get list of calendar entities first
        states = ha_client.get_all_states()
        if isinstance(states, dict) and "error" in states:
            return "Error connecting to Home Assistant."
            
        calendar_entities = [s['entity_id'] for s in states if s['entity_id'].startswith('calendar.')]
        
        all_events = []
        for cal_id in calendar_entities:
            # HA API for calendar events: GET /api/calendars/{entity_id}?start={start}&end={end}
            url = f"{ha_client.base_url}/api/calendars/{cal_id}"
            params = {"start": start_str, "end": end_str}
            
            # We use the internal requests session from ha_client to keep auth headers
            import requests
            res = requests.get(url, headers=ha_client.headers, params=params, timeout=5)
            
            if res.status_code == 200:
                events = res.json()
                for e in events:
                    # Simplify output
                    summary = e.get("summary", "Unknown Event")
                    start_dt = e.get("start", {}).get("dateTime", "") or e.get("start", {}).get("date", "")
                    all_events.append(f"- [{start_dt}] {summary} ({cal_id})")

        if not all_events:
            return "No events found."
            
        # Sort chronologically (simple string sort usually works for ISO dates)
        all_events.sort()
        return "\n".join(all_events)

    except Exception as e:
        return f"Failed to fetch calendar: {e}"

# region WEATHER & ENV (Home Assistant)
@tool
def get_weather_report() -> str:
    """
    Fetches current weather and environmental alerts (Allergy, Air Quality).
    """
    try:
        states = ha_client.get_all_states()
        if isinstance(states, dict): return "Error reading HA states."
        
        report = []
        
        # Find Main Weather Entity
        weather = next((s for s in states if s['entity_id'].startswith('weather.')), None)
        if weather:
            attrs = weather.get("attributes", {})
            temp = attrs.get("temperature", "?")
            cond = weather.get("state", "unknown")
            report.append(f"Weather: {cond}, {temp}°{attrs.get('temperature_unit', 'F')}")
        
        # Find Environmental Sensors (Allergy, AQI)
        # We look for keywords in entity_ids
        for s in states:
            eid = s['entity_id']
            state = s['state']
            if "allergy" in eid or "aqi" in eid or "air_quality" in eid:
                name = s.get("attributes", {}).get("friendly_name", eid)
                report.append(f"Environment: {name} is {state}")

        if not report:
            return "No weather data found."
            
        return "\n".join(report)

    except Exception as e:
        return f"Weather Error: {e}"

# region MAINTENANCE LOGGING (SQL)
@tool
def log_maintenance(task_name: str, date_performed: str, 
                   metric_value: int = 0, metric_unit: str = "", 
                   next_due_months: int = 0, next_due_miles: int = 0,
                   notes: str = "") -> str:
    """
    Logs a completed maintenance task.
    Args:
        date_performed: YYYY-MM-DD
        next_due_months: How many months until due again (calculates next_due_date).
        next_due_miles: How many miles/hours to add to current metric (calculates next_due_metric).
    """
    session = get_db_session()
    try:
        # Calculate Next Due Date
        dt_performed = datetime.strptime(date_performed, "%Y-%m-%d").date()
        next_date = None
        if next_due_months > 0:
            # Rough calculation
            import dateutil.relativedelta
            next_date = dt_performed + dateutil.relativedelta.relativedelta(months=+next_due_months)

        # Calculate Next Metric
        next_metric = None
        if next_due_miles > 0 and metric_value > 0:
            next_metric = metric_value + next_due_miles

        entry = MaintenanceLog(
            task_name=task_name,
            date_performed=dt_performed,
            metric_value=metric_value,
            metric_unit=metric_unit,
            notes=notes,
            next_due_date=next_date,
            next_due_metric=next_metric,
            status="completed" # The log itself is complete, but it implies a future deadline
        )
        session.add(entry)
        session.commit()
        return f"Logged: {task_name}. Next due: {next_date} or {next_metric} {metric_unit}."
    except Exception as e:
        return f"Database Error: {e}"
    finally:
        session.close()

# region CHECK MAINTENANCE STATUS (SQL)
@tool
def check_maintenance_status() -> str:
    """
    Checks for upcoming or overdue maintenance.
    """
    session = get_db_session()
    try:
        # We find the *latest* entry for each task name to see if it's due
        # Simple Logic: Query all, process in python for flexibility
        logs = session.query(MaintenanceLog).all()
        
        if not logs:
            return "No maintenance history found."

        # Group by task
        task_status = {}
        for log in logs:
            # We only care about the most recent log for a given task
            if log.task_name not in task_status:
                task_status[log.task_name] = log
            else:
                if log.date_performed > task_status[log.task_name].date_performed:
                    task_status[log.task_name] = log
        
        report = []
        today = date.today()
        
        for task, log in task_status.items():
            # Check Time
            if log.next_due_date:
                days_left = (log.next_due_date - today).days
                if days_left < 0:
                    report.append(f"[OVERDUE] {task}: Due {log.next_due_date} ({abs(days_left)} days ago)")
                elif days_left < 30:
                    report.append(f"[UPCOMING] {task}: Due {log.next_due_date} (in {days_left} days)")
            
            # Metric checking would require user input of *current* mileage
            # For now, we just list the target
            if log.next_due_metric:
                 report.append(f"[TRACKING] {task}: Next due at {log.next_due_metric} {log.metric_unit}")

        if not report:
            return "All maintenance is up to date."
            
        return "\n".join(report)

    except Exception as e:
        return f"Error checking status: {e}"
    finally:
        session.close()