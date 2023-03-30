from datetime import datetime, timedelta

def parse_date_or_weekday(s):
    try:
        # try to parse s as a date string
        return datetime.strptime(s, '%d/%m/%Y').date()
    except ValueError:
        # if s is not a valid date, assume it's a weekday
        return parse_weekday(s)

def parse_weekday(s):
    weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    s = s.lower()
    if s not in weekdays:
        raise ValueError(f'Invalid weekday: {s}')
    today = datetime.today().date()
    days_ahead = (weekdays.index(s) - today.weekday()) % 7
    return today + timedelta(days=days_ahead)

def parse_range(s):
    start_str, end_str = s.split('-', maxsplit=1)
    start = parse_date_or_weekday(start_str.strip())
    end = parse_date_or_weekday(end_str.strip())
    if end < start:
        raise ValueError('End date is before start date')
    return [start + timedelta(days=i) for i in range((end-start).days + 1)]


def parse_list(s):
    return [parse_date_or_weekday(x.strip()) for x in s.split(',')]

def parse_days(s):
    # remove any trailing commas
    s = s.rstrip(',')
    if '-' in s:
        return parse_range(s)
    elif ',' in s:
        return parse_list(s)
    else:
        return [parse_date_or_weekday(s)]

def main():
    days = input('Enter days: ')
    dates = parse_days(days)
    for date in dates:
        print(date.strftime('%d/%m/%Y'))

if __name__ == '__main__':
    main()
