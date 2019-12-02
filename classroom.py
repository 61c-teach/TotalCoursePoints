"""
This is the classroom and its info.
"""
from .assignment import Category
from .grade_bins import GradeBins
from .student import Student
from .utils import GSheetExtensions, Time, bar_plot_str
import csv
import json
import datetime
import pytz
from collections import OrderedDict
import sys

NAME_MARKER = "Name"
EMAIL_MARKER = "Email"
SID_MARKER = "SID"
SECRET_MARKER = "Secret"
EXTENSIONS_MARKER = "Extensions"
ACTIVESTUDENT_MARKER = "InCanvas"

class Classroom:
    def __init__(self, name: str, class_id: str, grade_bins: GradeBins, categories: dict={}, students: list=[], gsheets_grades=None, timezone=pytz.timezone("America/Los_Angeles"), raw_additional_pts: float=0):
        self.grade_bins = grade_bins
        self.categories = categories
        self.students = students
        self.name = name
        self.class_id = class_id
        self.gsheets_grades = gsheets_grades
        self.timezone = timezone
        self.raw_additional_pts = raw_additional_pts
        self.set_time_now()
        self.reset_comment()
        self.reset_welcome()
        self.append_welcome(f"Welcome to the Total Course Points Autograder for [{class_id}] {name}!")
        self.append_welcome(f"This autograder is designed to increase the transparency of {class_id}'s grading.", end="\n\n")
        self.append_welcome(f"[WARN]: This is a prototype grade calculator so it may have bugs! Please report bugs to course staff if you see any.", end="\n\n")

    def append_welcome(self, *args, sep=' ', end='\n'):
        self.welcome_message += sep.join(args) + end

    def reset_welcome(self):
        self.welcome_message = ""
    
    def get_welcome(self):
        return self.welcome_message + f"[INFO]: The last calculation was at {self.get_localized_time()}\n\n"

    def append_comment(self, *args, sep=' ', end='\n'):
        self.global_comment += sep.join(args) + end

    def reset_comment(self):
        self.global_comment = ""
    
    def get_comment(self):
        return self.global_comment
    
    def get_raw_time(self):
        return self.time
    
    def get_localized_time(self):
        # return self.timezone.localize(self.time)
        return self.time.astimezone(self.timezone)
    
    def set_time(self, time):
        self.time = time

    def set_time_now(self):
        self.time = datetime.datetime.utcnow()

    def get_raw_additional_pts(self):
        return self.raw_additional_pts
    
    def set_raw_additional_pts(self, pts: float):
        self.raw_additional_pts = pts

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
                active_student = str(row.get(ACTIVESTUDENT_MARKER))
                if sid is None:
                    print("Row does not have active student {}".format(row))
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
                s = Student(name, sid, email, active_student=active_student == "True", extensionData=extension, secret=secret)
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
        print("Processing classroom data...")
        print("Matching assignments to students...")
        self.match_assignments_to_students()
        print("Applying extensions...")
        self.apply_extensions(with_gsheet_extensions=with_gsheet_extensions)
        print("Applying slip days...")
        self.apply_slip_days()
        print("Done Processing Classroom Data!")

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
                cat.gen_active_students_scores(self)

    def apply_extensions(self, with_gsheet_extensions=None, process_gsheet_cell=lambda cell: Time(days=cell)):
        if with_gsheet_extensions is not None:
            try:
                gse = GSheetExtensions(with_gsheet_extensions)
                extensions = gse.get_all_extensions(process_gsheet_cell=process_gsheet_cell)
                if extensions is not None:
                    for sid, exts in extensions.items():
                        student = self.get_student(str(sid))
                        if student:
                            ed = student.extensionData
                            for ext, info in exts.items():
                                if ext in ed:
                                    edat = ed[ext]
                                    for a, t in info.items():
                                        edat[a] = process_gsheet_cell(t)
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
            # if str(student.sid) == "3031857271":
            #     import ipdb; ipdb.set_trace()
            student.apply_extensions()

    def apply_slip_days(self):
        for student in self.students:
            student.apply_slip_days()

    def all_inputted(self, with_hidden=False) -> bool:
        for c in self.categories.values():
            if not c.all_inputted(with_hidden=with_hidden):
                return False
        return True

    def get_grade_bins_count(self):
        grade_bin_counts = {}
        for student in self.students:
            if student.active_student:
                gb = student.get_approx_grade_id(self)
                if gb not in grade_bin_counts:
                    grade_bin_counts[gb] = 1
                else:
                    grade_bin_counts[gb] += 1
        return grade_bin_counts

    def get_class_gpa_average(self, grade_bins_count=None):
        if grade_bins_count is None:
            grade_bins_count = self.get_grade_bins_count()
        total_count = 0
        total_pts = 0
        for gbin in self.grade_bins.get_bins():
            gbid = gbin.id
            if gbid in grade_bins_count:
                count = grade_bins_count[gbid]
                total_count += count
                total_pts += gbin.get_gpa_value() * count
        if total_count == 0:
            return 0
        return total_pts / total_count

    def get_class_statistics_str(self, grade_bin_counts=None, graph=True):
        """This will print things like how many students, how many of each grade, etc...."""
        normal_grade_bins = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]
        if grade_bin_counts is None:
            grade_bin_counts = self.get_grade_bins_count()
        ave_gpa = self.get_class_gpa_average(grade_bin_counts)
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
            gbc_str = bar_plot_str(ordered_grades)
        else:
            for gb in normal_grade_bins:
                if gb in grade_bin_counts:
                    count = grade_bin_counts[gb]
                    gbc_str += f"{gb}: {count}\n"
                    del grade_bin_counts[gb]
            extra = "\n".join([f"{gb}: {count}" for gb, count in grade_bin_counts.items()])
            if extra != "":
                gbc_str += f"\n{extra}"
        return f"Number of students per grade bin:\n{gbc_str}\nClass average: {ave_gpa}\n"

    def print_class_statistics(self):
        print(self.get_class_statistics_str())

    
    def est_gpa(self, min_ave_gpa, start_pts=1, max_pts=20):
        base_raw_points = self.get_raw_additional_pts()
        for i in range(start_pts, 1 + max_pts):
            self.set_raw_additional_pts(i)
            gbc = self.get_grade_bins_count()
            ave_gpa = self.get_class_gpa_average(gbc)
            print(f"Stats when adding {i} points(s):\n{self.get_class_statistics_str(gbc)}")
            if ave_gpa >= min_ave_gpa:
                print("Found the minimum number of points to reach the ave gpa wanted!")
                self.set_raw_additional_pts(base_raw_points)
                return i
        print("Could not reach the minimum average gpa for the given number of iterations!")
        self.set_raw_additional_pts(base_raw_points)
        return False
        

    def dump_student_results(self, filename: str, approx_grade=False, skip_non_roster=True) -> None:
        """This function will dump the students in the class in a csv file."""
        csv_columns = ["name", "sid", "email", "grade", "score"]
        with open(filename, "w+") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            base_str = f"Dumping student {{}} / {len(self.students)} ({{}})"
            print(base_str.format(0, None))
            counter = 0
            for student in self.students:
                counter += 1
                sys.stdout.write("\033[F\033[K")
                print(base_str.format(counter, student.name))
                if not student.active_student:
                    continue
                sdata = student.get_raw_data(self, approx_grade=approx_grade)
                d = {}
                for idv in csv_columns:
                    d[idv] = sdata[idv]
                writer.writerow(d)
            
            sys.stdout.write("\033[F\033[K")
            print("Finished dumping classroom data!")