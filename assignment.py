"""
This stores the assignment data.
"""

from __future__ import annotations
from math import ceil
import numpy
import csv
from typing import Callable
from .utils import GSheetBase, safe_cast

SID_MARKER = "SID"
NAME_MARKER = "Name"
EMAIL_MARKER = "Email"
DAYS_LATE_MAKER = "Lateness (H:M:S)"
SCORE_MARKER = "Total Score"

class Assignment:
    default_gsheet_id = None
    default_gsheet_base = None
    use_gsheet_grades = None
    def __init__(self, 
        id: str,
        category, 
        name: str = None, 
        data_file: str = None,
        data_sheet: str = None,
        course_points: float = 0,
        percentage: float = None,
        late_penalty: float = None,
        allowed_slip_days: int = None,
        comment: str = "",
        show_stats: bool = None,
        show_rank: bool = None,
        out_of: float=None, 
        hidden: bool=False,
        additional_points: float=0,
        gsheets_grades=None,
    ):
        self.id = id
        self.name = name
        self.category = category
        self.course_points = course_points
        if data_file is None:
            self.data_file = "files/{}/{}.csv".format(category.name, id)
        else:
            self.data_file = data_file
        if data_sheet is None:
            self.data_sheet = f"{category.name}/{id}"
        else:
            self.data_sheet = data_sheet
        if out_of is not None:
            self.out_of = out_of
        elif self.category.out_of is not None:
            self.out_of = self.category.out_of
        else:
            self.out_of = self.course_points
        if show_stats is None:
            show_stats = category.show_stats
        self.show_stats = show_stats
        if show_rank is None:
            show_rank = category.show_rank
        self.show_rank = show_rank
        self.comment = comment
        self.allowed_slip_days = allowed_slip_days
        if late_penalty is None:
            late_penalty = category.late_penalty
        self.late_penalty = late_penalty
        self.percentage = percentage
        self.hidden = hidden or category.hidden
        self.data = {}
        self.scores = []
        self.data_loaded = True
        self.additional_points = additional_points
        if gsheets_grades is None:
            gsheets_grades = self.default_gsheet_id
        try:
            self.load_file()
        except Exception as exc:
            if gsheets_grades is not None and gsheets_grades or gsheets_grades is None and self.use_gsheet_grades:
                try:
                    self.load_gsheet(gsheets_grades)
                except Exception as e:
                    print(f"Failed to load grades from gsheet for {id}")
                    self.data_loaded = False
            else:
                self.data_loaded = False
                print("Failed to load file {}.".format(self.data_file))

    def load_gsheet(self, gsheet, data_sheet: str=None):
        if data_sheet is None:
            data_sheet = self.data_sheet
        if self.default_gsheet_base is not None and self.default_gsheet_base.sheet_key == gsheet:
            gdata = self.default_gsheet_base
        else:
            gdata = GSheetBase(gsheet)
        data = gdata.get_worksheet_records(data_sheet)
        self.load_data(data)

    def load_file(self, data_file: str=None):
        if data_file is None:
            data_file = self.data_file

        with open(data_file) as csvfile:
            reader = csv.DictReader(csvfile)
            self.load_data(reader)
    
    def load_data(self, data):
        for row in data:
                score = safe_cast(row.get(SCORE_MARKER), float)
                score = 0 if not score else float(score)
                sid = str(row.get(SID_MARKER))
                name = row.get(NAME_MARKER)
                email = row.get(EMAIL_MARKER)
                days_late = 0
                lateness = row.get(DAYS_LATE_MAKER)
                if isinstance(lateness, str):
                    lateness = lateness.split(':')
                    if len(lateness) == 3:
                        lateness = [int(x) for x in lateness]
                        if lateness[2] > 0:
                            lateness[1] += 1
                        if lateness[1] > 0:
                            lateness[0] += 1
                        days_late = lateness[0] / 24
                sad = StudentAssignmentData(score, days_late, name, sid, email, self)
                self.scores.append(sad.score)
                dat = self.data.get(sid)
                if dat is None:
                    self.data[sid] = sad
                else:
                    if isinstance(dat, list):
                        dat.append(sad)
                    else:
                        self.data[sid] = [dat, sad]
                if sid in self.data:
                    if isinstance(self.data[sid], list):
                        self.data[sid].append(sad)

    def get_student_data(self, student: Student) -> StudentAssignmentData:
        if not self.data_loaded:
            return StudentAssignmentData(
                0,
                0,
                student.name,
                student.sid,
                student.email,
                self,
                data_loaded=False
            )
        dat = self.data.get(student.sid)
        if isinstance(dat, list):
            for item in dat:
                if item.email == student.email:
                    return item
            for item in dat:
                if item.name == student.name:
                    return item
        if dat is None:
            return StudentAssignmentData(
                0,
                0,
                student.name,
                student.sid,
                student.email,
                self,
                data_loaded=True,
                data_found=False
            )
        return dat

    def get_total_possible(self):
        if self.percentage is None:
            return self.course_points
        else:
            if self.percentage is True:
                return self.category.course_points / sum([1 for a in self.category.assignments if a.percentage is True])
            return self.category.course_points * self.percentage

    def get_rank(self, score: float) -> tuple:
        rank = 1
        for s in self.scores:
            if s > score:
                rank += 1
        return rank
    
    def get_stats(self) -> tuple:
        if len(self.scores) == 0:
            return 0, 0, 0, 0, 0
        self.mean = numpy.mean(self.scores)
        self.median = numpy.median(self.scores)
        self.std = numpy.std(self.scores)
        self.max = max(self.scores)
        self.min = min(self.scores)
        return (self.mean, self.median, self.std, self.max, self.min)
    
    def get_stats_str(self) -> str:
        if not self.data_loaded:
            return ""
        stats = self.get_stats()
        return "mean: {}\nmedian: {}\nstd dev: {}\nmax: {}\nmin: {}\n".format(*stats)


class StudentAssignmentData:
    def __init__(self, 
            score: float, 
            days_late: float, 
            name: str, 
            sid: str, 
            email: str, 
            assignment: Assignment, 
            slip_days_used: int=0, 
            extension_days: int=0,
            data_loaded: bool=True,
            data_found: bool=True
        ):
        if days_late is None:
            days_late = 0
        else:
            self.days_late = ceil(days_late)
        self.score = 0 if not score else float(score)
        self.assignment = assignment
        self.name = name
        self.sid = sid
        self.email = email
        self.slip_days_used = slip_days_used
        self.extension_days = extension_days
        self.data_loaded = data_loaded
        self.data_found = data_found
        self.get_total_possible = assignment.get_total_possible

    def is_hidden(self):
        return self.assignment.hidden

    def get_late_days(self):
        return max(0, self.days_late - self.slip_days_used - self.extension_days)

    def get_course_points(self, with_additional_points: bool=True, convert_to_course_points=True):
        late_days = self.get_late_days()
        penalty = 1 - min(late_days * self.assignment.late_penalty, 1)
        score = self.score + (self.assignment.additional_points if with_additional_points else 0)
        if convert_to_course_points:
            score *= (self.assignment.get_total_possible() / self.assignment.out_of)
        return penalty * score
    
    def get_str(self):
        s = "{}[{}] {}\n{}\n**********\n".format("(hidden) " if self.is_hidden() else "", self.assignment.id, self.assignment.name if self.assignment.name else "", self.assignment.comment)
        entered = False
        if self.assignment.get_total_possible() == 0:
            s += "This assignment is not worth any course points!"
            score = None
            course_points = None
        elif not self.assignment.data_loaded:
            s += "The scores for this assignment have not been entered yet!\n"
            score = "-"
            course_points = "-"
        elif self.assignment.data_loaded and not self.data_found:
            s += "Could not find a score for this assignment!"
            entered = True
            score = 0
            course_points = 0
        else:
            entered = True
            score = self.score
            if self.days_late > 0:
                s += "raw score: {} / {}\n".format(score, self.assignment.out_of)
                s += "days late: {}\n".format(self.days_late)
                if self.extension_days > 0:
                    s += "extension days: {}\n".format(self.extension_days)
                if self.assignment.category.max_slip_days is not None:
                    s += "slip days: {}\n".format(self.slip_days_used)
                s += "late days: {}\n".format(self.get_late_days())
                score = self.get_course_points(convert_to_course_points=False)
            course_points = self.get_course_points()
        
        if score is not None or course_points is not None:
            s += "score: {} / {}\n".format(score, self.assignment.out_of)
            s += "course points: {} / {}\n\n".format(course_points, self.get_total_possible())
        
        if entered:
            if self.assignment.show_rank:
                if score == "-" or score is None:
                    rnk = "N/A"
                else:
                    rnk = self.assignment.get_rank(score)
                s += "rank: {} / {}\n".format(rnk, len(self.assignment.scores))

            if self.assignment.show_stats:
                s += self.assignment.get_stats_str()
        s += "\n----------\n\n"
        return s


from .category import Category, StudentCategoryData
from .student import Student
