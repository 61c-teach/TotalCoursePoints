"""
This is the classroom and its info.
"""
from .assignment import Category
from .grade_bins import GradeBins
from .student import Student
from .utils import GSheetExtensions
import csv
import json
import datetime

NAME_MARKER = "Name"
EMAIL_MARKER = "Email"
SID_MARKER = "SID"
SECRET_MARKER = "Secret"
EXTENSIONS_MARKER = "Extensions"

class Classroom:
    def __init__(self, name: str, class_id: str, grade_bins: GradeBins, categories: dict={}, students: list=[], gsheets_grades=None):
        self.grade_bins = grade_bins
        self.categories = categories
        self.students = students
        self.name = name
        self.class_id = class_id
        self.gsheets_grades = gsheets_grades
        self.time = datetime.datetime.now()

    def get_time(self):
        return self.time
    
    def set_time(self, time):
        self.time = time

    def set_time_now(self):
        self.time = datetime.datetime.now()

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        # import ipdb; ipdb.set_trace()
        return "{} ({})\n{}\nStudents:\n{}".format(self.name, self.class_id, self.grade_bins, "\n".join(map(str, self.students)))

    def add_student(self, s: Student):
        self.students.append(s)

    def get_student(self, sid: str):
        sid = str(sid)
        for s in self.students:
            if sid == s.sid:
                return s

    def remove_student(self, s: Student):
        if s in self.students:
            self.students.remove(s)

    def add_category(self, c: Category):
        self.categories[c.name] = c

    def remove_category(self, c: str):
        # This is broken
        if c in self.categories:
            del self.categories[c]

    def load_students_from_roster(self, f: str, only_load: str = None):
        """
        Reads a roster and creates students from each row.
        Required Columns: Name (str), Email (str), SID (str)
        Optional Columns: Secret (str), Extensions (json)
        Extensions should be a dictionary indexed by category name and assignment id

        only_load will only load the rows with matching student id if it is not none.
        """
        with open(f) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                name = row.get(NAME_MARKER)
                if name is None:
                    print("Row does not have a name! {}".format(row))
                    continue
                email = row.get(EMAIL_MARKER)
                if email is None:
                    print("Row does not have an email! {}".format(row))
                    continue
                sid = str(row.get(SID_MARKER))
                if sid is None:
                    print("Row does not have a SID! {}".format(row))
                    continue
                secret = row.get(SECRET_MARKER)
                extension = row.get(EXTENSIONS_MARKER)
                if extension:
                    try:
                        extension = json.loads(extension)
                    except Exception as exc:
                        print(exc)
                        print("Could not load extensions for student {} with sid {}! Here is the extension data: {}".format(name, sid, extension))
                        extension = None
                s = Student(name, sid, email, extensionData=extension, secret=secret)
                self.add_student(s)

    def get_total_possible(self, with_hidden=False, only_inputted=False) -> int:
        points = 0
        for cat in self.categories.values():
            if cat.hidden and not with_hidden:
                continue
            points += cat.get_total_possible(with_hidden=with_hidden, only_inputted=only_inputted)
        return points

    def process(self, with_gsheet_extensions=None):
        """
        This function will go through each assigment and get the score for each student.
        """
        # Since we are making assignments load data when they get created, we should not be calling this.
        # self.load_assignment_data()
        self.match_assignments_to_students()
        self.apply_extensions(with_gsheet_extensions=with_gsheet_extensions)
        self.apply_slip_days()

    def load_assignment_data(self):
        for category in self.categories.values():
            category.load_assignment_data()

    def match_assignments_to_students(self):
        for student in self.students:
            for cat in self.categories.values():
                # import ipdb
                # ipdb.set_trace()
                cat_data = cat.get_student_data(student)
                student.add_category_data(cat_data)

    def apply_extensions(self, with_gsheet_extensions=None):
        if with_gsheet_extensions is not None:
            try:
                gse = GSheetExtensions(with_gsheet_extensions)
                extensions = gse.get_all_extensions()
                if extensions is not None:
                    for sid, exts in extensions.items():
                        student = self.get_student(str(sid))
                        if student:
                            ed = student.extensionData
                            for ext, info in exts.items():
                                if ext in ed:
                                    edat = ed[ext]
                                    for a, days in info.items():
                                        edat[a] = days
                                else:
                                    ed[ext] = info
                        else:
                            print("Found extensions for student not in the roster! ({})".format(sid))
                else:
                    print("Getting all extensions returned none.")
            except Exception as e:
                print("An error occured when fetching gsheet extensions!")
                import traceback
                traceback.print_exc()
                print(e)
        for student in self.students:
            student.apply_extensions()

    def apply_slip_days(self):
        for student in self.students:
            student.apply_slip_days()

    def all_inputted(self, with_hidden=False) -> bool:
        for c in self.categories.values():
            if not c.all_inputted(with_hidden=with_hidden):
                return False
        return True


    def print_class_statistics(self):
        """This will print things like how many students, how many of each grade, etc...."""
        pass

    def dump_student_results(self, filename: str) -> None:
        """This function will dump the students in the class in a csv file."""
        
        pass