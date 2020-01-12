"""
This is the classroom and its info.
"""
from .assignment import Category
from .grade_bins import GradeBins
from .student import Student
from .utils import GSheetExtensions, Time, bar_plot_str, get_class_gpa_average, get_class_statistics_str
import csv
import json
import datetime
import pytz
from collections import OrderedDict
import sys
import numpy as np

NAME_MARKER = "Name"
EMAIL_MARKER = "Email"
SID_MARKER = "SID"
SECRET_MARKER = "Secret"
EXTENSIONS_MARKER = "Extensions"
ACTIVESTUDENT_MARKER = "InCanvas"
GRADE_STATUS_MARKER = "ForGrade"
INCOMPLETE_MARKER = "Incomplete"

class Classroom:
    def __init__(self, name: str, class_id: str, grade_bins: GradeBins, categories: dict={}, students: list=[], gsheets_grades=None, timezone=pytz.timezone("America/Los_Angeles"), raw_additional_pts: float=0, gs_leaderboard: bool=False):
        self.grade_bins = grade_bins
        self.categories = categories
        self.students = students
        self.name = name
        self.class_id = class_id
        self.gsheets_grades = gsheets_grades
        self.timezone = timezone
        self.raw_additional_pts = raw_additional_pts
        self.gs_leaderboard = gs_leaderboard
        self.set_time_now()
        self.reset_comment()
        self.reset_welcome()
        self.append_welcome(f"Welcome to the Total Course Points Autograder for [{class_id}] {name}!")
        self.append_welcome(f"This autograder is designed to increase the transparency of {class_id}'s grading.", end="\n\n")
        self.append_welcome(f"[WARN]: This is a prototype grade calculator so it may have bugs! Please report bugs to course staff if you see any.", end="\n\n")
        self.ignore_categories = set([])

    def add_ignore_category(self, name):
        self.ignore_categories.add(name)
    
    def remove_ignore_category(self, name):
        self.ignore_categories.remove(name)
    
    def get_ignore_category(self):
        return self.ignore_categories

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

    def get_category(self, c: str):
        return self.categories.get(c)
    
    def get_student_ranking(self, s: Student, only_active_students=True, with_hidden=False):
        s_total_pts = s.get_total_points_with_class(self, with_hidden=with_hidden)
        all_points = []
        for student in self.students:
            if only_active_students and not student.active_student:
                continue
            all_points.append(student.get_total_points_with_class(self, with_hidden=with_hidden))
        all_points = sorted(all_points, reverse=True)
        rank = 1
        for s in all_points:
            if s > s_total_pts:
                rank += 1
        return (rank, len(all_points))
    
    def get_student_ranking_str(self, s: Student, only_active_students=True, with_hidden=False):
        rank, total_students = self.get_student_ranking(s, only_active_students=only_active_students, with_hidden=with_hidden)
        return f"Student {s.name} ({s.sid}) is rank {rank} / {total_students}"

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
                if active_student is None:
                    print("Row does not have active student {}".format(row))
                    continue
                grade_status = str(row.get(GRADE_STATUS_MARKER))
                if grade_status is None:
                    print("Row does not have for grade status {}".format(row))
                    continue
                incomplete = row.get(INCOMPLETE_MARKER)
                if grade_status is None:
                    print("Row does not have for incomplete status {}".format(row))
                    continue
                incomplete = incomplete == "True"
                secret = row.get(SECRET_MARKER)
                extension = row.get(EXTENSIONS_MARKER)
                if extension:
                    try:
                        extension = json.loads(extension)
                    except Exception as exc:
                        print(exc)
                        print("Could not load extensions for student {} with sid {}! Here is the extension data: {}".format(name, sid, extension))
                        extension = None
                s = Student(name, sid, email, active_student=active_student == "True", extensionData=extension, secret=secret, grade_status=grade_status, incomplete=incomplete)
                self.add_student(s)

    def get_total_possible(self, with_hidden=False, only_inputted=False) -> int:
        points = 0
        for cat in self.categories.values():
            if cat.hidden and not with_hidden:
                continue
            points += cat.get_total_possible(with_hidden=with_hidden, only_inputted=only_inputted)
        return points

    def process(self, with_gsheet_extensions=None, only_active_students=True):
        """
        This function will go through each assigment and get the score for each student.
        """
        # Since we are making assignments load data when they get created, we should not be calling this.
        # self.load_assignment_data()
        print("Processing classroom data...")
        if only_active_students:
            print("Generating active student data...")
            for cat in self.categories.values():
                cat.gen_active_students_scores(self)
        print("Matching assignments to students...")
        self.match_assignments_to_students()
        print("Applying extensions...")
        self.apply_extensions(with_gsheet_extensions=with_gsheet_extensions)
        print("Applying slip time...")
        self.apply_slip_time()
        print("Dropping lowest assignments...")
        self.drop_lowest_assignments()
        print("Done Processing Classroom Data!")

    def load_assignment_data(self):
        for category in self.categories.values():
            category.load_assignment_data()

    def match_assignments_to_students(self):
        for student in self.students:
            for cat in self.categories.values():
                cat_data = cat.get_student_data(student)
                student.add_category_data(cat_data)

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

    def apply_slip_time(self):
        for student in self.students:
            student.apply_slip_time()

    def drop_lowest_assignments(self):
        for student in self.students:
            student.drop_lowest_assignments()

    def all_inputted(self, with_hidden=False) -> bool:
        for c in self.categories.values():
            if not c.all_inputted(with_hidden=with_hidden):
                return False
        return True

    def get_grade_bins_count(self, with_hidden=False, inlcude_pnp=False):
        grade_bin_counts = {}
        all_in = self.all_inputted()
        for student in self.students:
            if student.active_student and (inlcude_pnp or student.is_for_grade()):
                if all_in:
                    gb = student.get_grade(self, with_hidden=with_hidden)
                else:
                    gb = student.get_approx_grade_id(self, with_hidden=with_hidden)
                if gb not in grade_bin_counts:
                    grade_bin_counts[gb] = 1
                else:
                    grade_bin_counts[gb] += 1
        return grade_bin_counts

    def get_class_gpa_average(self, grade_bins_count=None, with_hidden=False):
        if grade_bins_count is None:
            grade_bins_count = self.get_grade_bins_count(with_hidden=with_hidden)
        return get_class_gpa_average(grade_bins_count, self.grade_bins)

    def get_class_statistics_str(self, grade_bin_counts=None, graph=True, with_hidden=False):
        """This will print things like how many students, how many of each grade, etc...."""
        normal_grade_bins = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]
        if grade_bin_counts is None:
            grade_bin_counts = self.get_grade_bins_count(with_hidden=with_hidden)
        return get_class_statistics_str(grade_bin_counts, self.grade_bins)

    def print_class_statistics(self, with_hidden=False):
        print(self.get_class_statistics_str(with_hidden=with_hidden))

    def get_class_points_stats_str(self, with_hidden=False, skip_non_roster=True):
        all_points = []
        for student in self.students:
            if skip_non_roster and not student.active_student:
                continue
            all_points.append(student.get_total_points_with_class(self, with_hidden=with_hidden))
        if len(all_points) == 0:
            all_points.append(0)
        mean = np.mean(all_points)
        median = np.median(all_points)
        std = np.std(all_points)
        pmax = np.max(all_points)
        pmin = np.min(all_points)
        return f"mean: {mean}\nmedian: {median}\nstd dev: {std}\nmax: {pmax}\nmin: {pmin}"

    def est_gpa(self, min_ave_gpa, start_pts=1, max_pts=20, max_a_plus=None, adjust_a_plus: bool=True, with_hidden=False):
        orig_bins = self.grade_bins
        base_raw_points = self.get_raw_additional_pts()
        have_max_a_plus = max_a_plus == 0
        a_plus_adjust = 0
        for i in range(start_pts, 1 + max_pts):
            if adjust_a_plus and max_a_plus is None:
                self.grade_bins = orig_bins.copy()
                self.grade_bins.increment_A_plus(i)
            if have_max_a_plus:
                a_plus_adjust += 1
                print(f"Adjusting A+ bin by {a_plus_adjust} points.")
                self.grade_bins = orig_bins.copy()
                self.grade_bins.increment_A_plus(a_plus_adjust)
            self.set_raw_additional_pts(i)
            gbc = self.get_grade_bins_count(with_hidden=with_hidden)
            a_plus = gbc.get("A+")
            a_plus = 0 if a_plus is None else a_plus
            ave_gpa = self.get_class_gpa_average(gbc)
            print(f"Stats when adding {i} points(s):\n{self.get_class_statistics_str(gbc)}")
            if ave_gpa >= min_ave_gpa:
                print("Found the minimum number of points to reach the ave gpa wanted!")
                if max_a_plus is not None and a_plus_adjust > 0:
                    print(f"The A+ bin must be shifted up by {a_plus_adjust} points!")
                self.set_raw_additional_pts(base_raw_points)
                self.grade_bins = orig_bins
                if a_plus_adjust > 0:
                    return (i, a_plus_adjust)
                return i
            
            if (not have_max_a_plus) and max_a_plus is not None and a_plus >= max_a_plus:
                print("Max A+ reached!")
                have_max_a_plus = True
        print("Could not reach the minimum average gpa for the given number of iterations!")
        self.set_raw_additional_pts(base_raw_points)
        self.grade_bins = orig_bins
        return False
        

    def dump_student_results(self, filename: str, approx_grade=False, skip_non_roster=True, include_assignment_scores=False, with_hidden=True) -> None:
        """This function will dump the students in the class in a csv file."""
        csv_columns = ["name", "sid", "email", "grade", "score", "Grading Basis"]

        if include_assignment_scores:
            for cat in self.categories.values():
                for assign in cat.assignments:
                    csv_columns.append(f"{cat.name}/{assign.id}")
            if self.get_raw_additional_pts() != 0:
                csv_columns.append("Raw Additional Pts")

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
                sdata = student.get_raw_data(self, approx_grade=approx_grade, with_hidden=with_hidden)
                if include_assignment_scores:
                    add_pts = self.get_raw_additional_pts()
                    if add_pts != 0:
                        sdata["Raw Additional Pts"] = add_pts
                d = {}
                for idv in csv_columns:
                    d[idv] = sdata[idv]
                writer.writerow(d)
            
            sys.stdout.write("\033[F\033[K")
            print("Finished dumping classroom data!")

    def gen_calcentral_report(self, dest_filename:str, calcentral_roster_filename:str, comment_fn=lambda sid: ""):
        csv_columns = ["SID", "Name", "Grade", "Grading Basis", "Comments"]
        name_map = {}
        with open(calcentral_roster_filename, "r+") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                sid = row.get("SID")
                name = row.get("Name")
                name_map[sid] = name
        with open(dest_filename, "w+") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            for student in self.students:
                if not student.active_student:
                    continue
                sdata = student.get_raw_data(self, approx_grade=False, with_hidden=True)
                d = {}
                d["SID"] = sdata["sid"]
                name = name_map.get(d["SID"])
                if name is None:
                    name = sdata['name']
                    print(f"Could not find student {name} ({d['SID']}) in the sid-name map. You will have to fix the SID and name!")
                else:
                    del name_map[d['SID']]
                d["Name"] = name
                d["Grade"] = sdata["grade"]
                d["Grading Basis"] = sdata["Grading Basis"]
                d["Comments"] = f"{round(sdata['score'], 2)}" + comment_fn(d["SID"])
                writer.writerow(d)
        print("-" * 20)
        print("Not matched names:")
        for sid, name in name_map.items():
            print(f"{name} ({sid})")