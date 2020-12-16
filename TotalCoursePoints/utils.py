import gspread
from gspread.exceptions import APIError
from time import sleep
import json
from oauth2client.service_account import ServiceAccountCredentials
import math
from collections import OrderedDict

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

class ResourceExhaustedError(Exception):
    pass

class GSheetCredentialsManager:
    SCOPE = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    def __init__(self, credentials_list: [str]):
        self.all_creds = [
            ServiceAccountCredentials.from_json_keyfile_name(credentials, self.SCOPE) 
            for credentials in credentials_list
            ]
        self.clients = []

    def get_clients(self):
        for i, cred in enumerate(self.all_creds):
            if i <= len(self.clients):
                self.clients.append(gspread.authorize(cred))
            yield self.clients[i]

    def safe_gspread_call(self, sheet_key, fn_name, args=[], kwargs={}, sleep_timeout=gspread_timeout, attempts=gspread_attempts):
        i = 0
        cond = lambda: attempts <= 0 or i < attempts
        def attempt(fn):
            raise_error = None
            try:
                return fn(*args, *kwargs)
            except APIError as e:
                raise_error = e
            if raise_error is not None:
                e: Exception = raise_error
                raise_resource_error = False
                try:
                    if json.loads(e.response.text)["error"]["status"] == RESOURCE_EXHAUSTED:
                        raise_resource_error = True
                    else:
                        raise e
                except Exception:
                    raise e
                if raise_resource_error:
                    raise ResourceExhaustedError()
        while cond():
            j = 0
            for client in self.get_clients():
                try:
                    return attempt(getattr(client.open_by_key(sheet_key), fn_name))
                except ResourceExhaustedError as e:
                    print(f"Failed to use client {j}, trying a new one...")
                j += 1
            i += 1
            print(f"The resources have been exhausted (attempt: {i - 1})!" + (f" Retrying in {sleep_timeout} seconds..." if cond() else ""))
            if cond():
                sleep(sleep_timeout)
        print("Failed to grab resource!")


class GSheetBase:
    default_credentials = 'credentials.json'
    default_credentials_list = None
    def __init__(self, sheet_key, credentials=None, credentials_manager: GSheetCredentialsManager=None, prefetch=True):
        if credentials is None:
            credentials = self.default_credentials
        # scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
        # creds = ServiceAccountCredentials.from_json_keyfile_name(credentials, scope)
        # self.client = gspread.authorize(creds)
        if credentials_manager is None:
            if self.default_credentials_list is not None:
                credentials_manager = GSheetCredentialsManager(self.default_credentials_list)
            else:
                credentials_manager = GSheetCredentialsManager([credentials])
        self.cred_manager = credentials_manager
        # self.sheets = self.client.open_by_key(sheet_key)
        self.sheet_key = sheet_key
        self.sheet_data = None
        if prefetch:
            self.sheet_data = self.fetch_all_sheets()

    def fetch_all_sheets(self):
        # meta = safe_gspread_call(self.sheets.fetch_sheet_metadata)
        meta = self.cred_manager.safe_gspread_call(self.sheet_key, "fetch_sheet_metadata")
        ranges = [sheet['properties']['title'] for sheet in meta['sheets']]
        # data = safe_gspread_call(self.sheets.values_batch_get, [ranges])
        data = self.cred_manager.safe_gspread_call(self.sheet_key, "values_batch_get", args=[ranges])

        all_sheets = {}

        for sheet in data["valueRanges"]:
            sheet_name = sheet["range"].split("!")[0]
            if sheet_name.startswith("'"):
                sheet_name = sheet_name[1:]
            if sheet_name.endswith("'"):
                sheet_name = sheet_name[:-1]
            
            ssvalues = sheet["values"]

            keys = ssvalues[0]
            values = ssvalues[1:]

            all_sheets[sheet_name] = [dict(zip(keys, row)) for row in values]

        return all_sheets

    def get_worksheet_records(self, sheet_name):
        if self.sheet_data is not None:
            if sheet_name not in self.sheet_data:
                raise ValueError(f"{sheet_name} is not in the spreadsheet!")
            return self.sheet_data[sheet_name]
        try:
            # ws = self.sheets.worksheet(sheet_name)
            ws = self.cred_manager.safe_gspread_call(self.sheet_key, "worksheet", args=[sheet_name])
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
            _id = str(row[self.id_column])
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
        if self.sheet_data is None:
            worksheets = self.cred_manager.safe_gspread_call(self.sheet_key, "worksheets")
        else:
            worksheets = list(self.sheet_data.keys())
        extensions = {}
        for ws in worksheets:
            if isinstance(ws, str):
                title = ws
            else:
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

def bar_plot_str(data: {str:float}, number_of_bins: int=25, chunk_size: int=8, add_percents=False) -> str:
    max_value = max(count for count in data.values())
    increment = max_value / number_of_bins
    if increment == 0:
        increment = 1

    total = sum(data.values())
    if total == 0:
        total = 1

    longest_label_length = max(len(label) for label in data.keys())

    ret_str = ""

    for label, count in data.items():

        # The ASCII block elements come in chunks of 8, so we work out how
        # many fractions of 8 we need.
        # https://en.wikipedia.org/wiki/Block_Elements
        bar_chunks, remainder = divmod(int(count * chunk_size / increment), chunk_size)

        # First draw the full width chunks
        bar = '█' * bar_chunks

        # Then add the fractional part.  The Unicode code points for
        # block elements are (8/8), (7/8), (6/8), ... , so we need to
        # work backwards.
        if remainder > 0:
            bar += chr(ord('█') + (chunk_size - remainder))

        # If the bar is empty, add a left one-eighth block
        bar = bar or  '▏'
        ratio = str(round(count / total * 100, 1))
        if len(ratio) <= 4:
            ratio = (" " * (4 - len(ratio))) + ratio
        count_str = (" " * (len(str(max_value)) - len(str(count)))) + str(count)
        ret_str += f"{label.ljust(longest_label_length)} ▏ ({ratio}%) {count_str} {bar}\n"
    return ret_str

def get_class_gpa_average(grade_bins_count, grade_bins):
    total_count = 0
    total_pts = 0
    for gbin in grade_bins.get_bins():
        gbid = gbin.id
        if gbid in grade_bins_count:
            count = grade_bins_count[gbid]
            total_count += count
            total_pts += gbin.get_gpa_value() * count
    if total_count == 0:
        return 0
    return total_pts / total_count

def get_class_statistics_str(grade_bin_counts, grade_bins, graph=True):
    """This will print things like how many students, how many of each grade, etc...."""
    # normal_grade_bins = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]
    normal_grade_bins = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F", "P", "NP", "S", "U"]
    ave_gpa = get_class_gpa_average(grade_bin_counts, grade_bins)
    ordered_grades = OrderedDict()
    for ngb in normal_grade_bins:
        if ngb in grade_bin_counts:
            ordered_grades[ngb] = grade_bin_counts[ngb]
        else:
            ordered_grades[ngb] = 0
    for gb, val in grade_bin_counts.items():
        if gb in normal_grade_bins:
            continue
        ordered_grades[gb] = val
    gbc_str = ""
    if graph:
        gbc_str = bar_plot_str(ordered_grades, add_percents=True)
    else:
        for gb in normal_grade_bins:
            if gb in grade_bin_counts:
                count = grade_bin_counts[gb]
                gbc_str += f"{gb}: {count}\n"
                del grade_bin_counts[gb]
        extra = "\n".join([f"{gb}: {count}" for gb, count in grade_bin_counts.items()])
        if extra != "":
            gbc_str += f"\n{extra}"
    total = sum(ordered_grades.values())
    if total == 0:
        total = 1
    As = round((ordered_grades["A+"] + ordered_grades["A"] + ordered_grades["A-"]) / total * 100, 1)
    Bs = round((ordered_grades["B+"] + ordered_grades["B"] + ordered_grades["B-"]) / total * 100, 1)
    Cs = round((ordered_grades["C+"] + ordered_grades["C"] + ordered_grades["C-"]) / total * 100, 1)
    # Ds = round((ordered_grades["D+"] + ordered_grades["D"] + ordered_grades["D-"]) / total * 100, 1)
    Ds = round((ordered_grades["D"]) / total * 100, 1)
    Fs = round((ordered_grades["F"]) / total * 100, 1)
    Ps = round((ordered_grades["P"]) / total * 100, 1)
    NPs = round((ordered_grades["NP"]) / total * 100, 1)
    Ss = round((ordered_grades["S"]) / total * 100, 1)
    Us = round((ordered_grades["U"]) / total * 100, 1)
    ratio_str = f"A:  {As}%\nB:  {Bs}%\nC:  {Cs}%\nD:  {Ds}%\nF:  {Fs}%\nP:  {Ps}%\nNP: {NPs}%\nS:  {Ss}%\nU:  {Us}%\n"
    return f"Number of students per grade bin:\n{gbc_str}\nGrades Ratios:\n{ratio_str}\nClass average: {ave_gpa}\n"