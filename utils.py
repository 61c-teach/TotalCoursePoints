import gspread
from gspread.exceptions import APIError
from time import sleep
import json
from oauth2client.service_account import ServiceAccountCredentials
import math

# we want to wait 10 seconds before we try to do the request.
gspread_timeout = 10
# <= 0 means we will try till success. otherwise a positive value.
gspread_attempts = 500

RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"

# fn is the function you want to call
# args is a LIST Of args you want to put in.
# kwargs is a DICT of named args you want to put in.
# 
def safe_gspread_call(fn, args=[], kwargs={}, sleep_timeout=gspread_timeout, attempts=gspread_attempts):
    i = 0
    cond = lambda: attempts <= 0 or i < attempts
    while cond():
        try:
            return fn(*args, *kwargs)
        except APIError as e:
            try:
                if not json.loads(e.response.text)["error"]["status"] == RESOURCE_EXHAUSTED:
                    raise e
            except Exception:
                raise e
        i += 1
        print(f"The resources have been exhausted (attempt: {i - 1})!" + (f" Retrying in {sleep_timeout} seconds..." if cond() else ""))
        if cond():
            sleep(sleep_timeout)
    print("Failed to grab resource!")

class GSheetBase:
    def __init__(self, sheet_key, credentials='credentials.json'):
        scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials, scope)
        self.client = gspread.authorize(creds)
        self.sheets = self.client.open_by_key(sheet_key)
        self.sheet_key = sheet_key

    def get_worksheet_records(self, sheet_name):
        try:
            # ws = self.sheets.worksheet(sheet_name)
            ws = safe_gspread_call(self.sheets.worksheet, [sheet_name])
        except Exception as e:
            print("Encountered an error when accessing sheet {}.".format(sheet_name))
            print(e)
            return None
        # return ws.get_all_records()
        return safe_gspread_call(ws.get_all_records)

class GSheetExtensions(GSheetBase):
    id_column = "sid"
    ignore_columns = [id_column, "name", "Notes"]
    ignore_sheets = []

    # def __init__(self, sheet_key, credentials='credentials.json'):
    #     scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    #     creds = ServiceAccountCredentials.from_json_keyfile_name(credentials, scope)
    #     self.client = gspread.authorize(creds)
    #     self.sheets = self.client.open_by_key(sheet_key)

    # def get_worksheet_records(self, sheet_name):
    #     try:
    #         ws = self.sheets.worksheet(sheet_name)
    #     except Exception as e:
    #         print("Encountered an error when accessing sheet {}.".format(sheet_name))
    #         print(e)
    #         return None
    #     return ws.get_all_records()

    def get_sheet_extensions(self, sheet_name, process_gsheet_cell=lambda cell: Time(parse=cell)):
        data = self.get_worksheet_records(sheet_name)
        if data is None:
            return None
        linked = {}
        for row in data:
            _id = row[self.id_column]
            stdext = {}
            linked[_id] = stdext
            for col in row.keys():
                if col not in self.ignore_columns:
                    item = row[col]
                    if item == '':
                        continue
                    itm = safe_cast(item, int)
                    itm = process_gsheet_cell(itm)
                    if itm is not None:
                        stdext[col] = itm
                    else:
                        print("Invalid entry in worksheet {} for {}={}, column {}: {}".format(sheet_name, self.id_column, _id, col, item))
        return linked
    
    def get_all_extensions(self, process_gsheet_cell=lambda cell: Time(parse=cell)):
        # worksheets = self.sheets.worksheets()
        worksheets = safe_gspread_call(self.sheets.worksheets)
        extensions = {}
        for ws in worksheets:
            title = ws.title
            if title not in self.ignore_sheets:
                data = self.get_sheet_extensions(title, process_gsheet_cell=process_gsheet_cell)
                if data is None:
                    print("Could not load the extensions for sheet {}".format(title))
                    continue
                for sid, exts in data.items():
                    if sid not in extensions:
                        extensions[sid] = {}
                    extensions[sid][title] = exts
        return extensions

def safe_cast(val, to_type, default=None):
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default

class Time:
    def __init__(self, seconds=0, minutes=0, hours=0, days=0, sign=0, parse=None):
        if parse is not None:
            raise NotImplementedError("Parsing a string to time is not implemented yet!")
        if seconds is None:
            seconds = 0
        if minutes is None:
            minutes = 0
        if hours is None:
            hours = 0
        if days is None:
            days = 0
        if seconds < 0 or minutes < 0 or hours < 0 or days < 0:
            sign = -1
        self.sign = sign
        seconds = abs(seconds)
        minutes = abs(minutes)
        hours = abs(hours)
        days = abs(days)
        self.seconds = seconds % 60
        minutes += seconds // 60
        self.minutes = minutes % 60
        hours += minutes // 60
        self.hours = hours % 24
        self.days = days + hours // 24
    
    def get_seconds(self):
        return (self.seconds + 60 * (self.minutes + 60 * (self.hours + 24 * (self.days)))) * self.get_sign()

    def get_sign(self):
        return -1 if self.sign < 0 else 1

    def ceil_to_days(self) -> int:
        m = self.minutes
        h = self.hours
        d = self.days
        m += math.ceil(self.seconds / 60)
        h += math.ceil(m / 60)
        d += math.ceil(h / 24)
        return d
    
    def ceil_to_hours(self) -> int:
        m = self.minutes
        h = self.hours
        m += math.ceil(self.seconds / 60)
        h += math.ceil(m / 60)
        h += self.days * 24
        return h

    def __sub__(self, other):
        if isinstance(other, int):
            return self.get_seconds() - other
        if isinstance(other, Time):
            t = self.get_seconds() - other.get_seconds()
            if t < 0:
                return Time(seconds=t * -1, sign=-1)
            return Time(seconds=t)
        import ipdb; ipdb.set_trace()
        raise NotImplementedError()

    def __rsub__(self, other):
        if isinstance(other, int):
            return other - self.get_seconds()
        if isinstance(other, Time):
            t = other.get_seconds() - self.get_seconds()
            if t < 0:
                return Time(seconds=t * -1, sign=-1)
            return Time(seconds=t)
        raise NotImplementedError()

    def __mul__(self, other):
        if isinstance(other, int):
            return Time(seconds = self.get_seconds() * other)
        raise NotImplementedError()

    def __rmul__(self, other):
        return self.__mul__(other)


    def __str__(self):
        # sign = self.get_sign()
        # if sign < 0:
        #     sign = "- "
        # else:
        #     sign = " "
        # return f"{sign}{self.days}-{self.hours}:{self.minutes}:{self.seconds}"
        return self.pretty_time_str()

    def __repr__(self):
        return self.__str__()
    
    def get_count(self, interval: "Time"):
        count = 0
        if self.get_seconds() == 0:
            return count
        late_amt = self
        while True:
            count += 1
            late_amt = late_amt - interval
            if late_amt.get_seconds() <= 0:
                return count

    def _compare(self, other, method):
        try:
            if isinstance(other, int):
                seconds = other
            else:
                seconds = other.get_seconds()
            return method(self.get_seconds(), seconds)
        except (AttributeError, TypeError):
            # _cmpkey not implemented, or return different type,
            # so I can't compare with "other".
            return NotImplemented

    def __lt__(self, other):
        return self._compare(other, lambda s, o: s < o)

    def __le__(self, other):
        return self._compare(other, lambda s, o: s <= o)

    def __eq__(self, other):
        return self._compare(other, lambda s, o: s == o)

    def __ge__(self, other):
        return self._compare(other, lambda s, o: s >= o)

    def __gt__(self, other):
        return self._compare(other, lambda s, o: s > o)

    def __ne__(self, other):
        return self._compare(other, lambda s, o: s != o)

    def pretty_time_str(self):
        s = self.seconds
        m = self.minutes
        h = self.hours
        d = self.days
        sstr = "" if s == 0 else str(s) + " second"
        sstr += "" if sstr == "" or s == 1 else "s"
        mstr = "" if m == 0 else str(m) + " minute"
        mstr += "" if mstr == "" or m == 1 else "s"
        hstr = "" if h == 0 else str(h) + " hour"
        hstr += "" if hstr == "" or h == 1 else "s"
        dstr = "" if d == 0 else str(d) + " day"
        dstr += "" if dstr == "" or d == 1 else "s"
        st = dstr
        for tmpstr in [hstr, mstr, sstr]:
            if st != "" and tmpstr != "":
                st += " "
            st += tmpstr
        if st == "":
            st = "0 seconds"
        else:
            sign = "- " if self.get_sign() < 0 else ""
            st = f"{sign}{st}"
        return st

class GracePeriod:
    def __init__(self, time: Time=Time(), apply_to_all_late_time=False):
        self.time: Time = time
        self.apply_to_all_late_time: bool = apply_to_all_late_time