import datetime

def parse_date(date_str):
    """Parses a date string in the format DD/MM/YYYY and returns a datetime.date object."""
    return datetime.datetime.strptime(date_str, '%d/%m/%Y').date()

def parse_weekday(weekday_str):
    """Parses a weekday string (e.g. Monday) and returns the corresponding integer (0 = Monday, 1 = Tuesday, etc.)."""
    weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    weekday_num = weekdays.index(weekday_str.lower())
    return weekday_num

def get_dates_in_range(start_date, end_date):
    """Returns a list of dates between start_date and end_date (inclusive)."""
    dates = []
    curr_date = start_date
    while curr_date <= end_date:
        dates.append(curr_date)
        curr_date += datetime.timedelta(days=1)
    return dates

def parse_days(days_str):
    """Parses a string of days (dates or weekdays) and returns a list of datetime.date objects."""
    days = []
    if ',' in days_str:
        # The input contains a list of days
        for s in days_str.split(','):
            if '/' in s:
                # The day is a date
                days.append(parse_date(s.strip()))
            else:
                # The day is a weekday
                days.append(parse_weekday(s.strip()))
    elif '-' in days_str:
        # The input contains a range of dates
        start_str, end_str = days_str.split('-')
        if '/' in start_str:
            # The range is specified in dates
            start = parse_date(start_str.strip())
            end = parse_date(end_str.strip())
            days.extend(get_dates_in_range(start, end))
        else:
            # The range is specified in weekdays
            start = parse_weekday(start_str.strip())
            end = parse_weekday(end_str.strip())
            for i in range(start, end+1):
                days.append(i)
    else:
        # The input is a single date or weekday
        if '/' in days_str:
            # The day is a date
            days.append(parse_date(days_str.strip()))
        else:
            # The day is a weekday
            days.append(parse_weekday(days_str.strip()))
    return days

def main():
    days_str = input("Enter days: ")
    days = parse_days(days_str)
    for day in days:
        if isinstance(day, int):
            # The day is a weekday
            print(datetime.date.today() + datetime.timedelta(days=(day-datetime.date.today().weekday())%7))
        else:
            # The day is a date
            print(day)

if __name__ == '__main__':
    main()
