"""
This is a class which will contain info about the current student.
"""
from __future__ import annotations
import json
from . import GradeBins

class Student:
    def __init__(self, name: str, sid: str, email: str, active_student: bool=True, grade_status: str="GRD", extensionData: dict={}, secret: str=None, incomplete: bool=False):
        self.name = name
        self.sid = str(sid)
        self.email = email
        self.active_student = active_student
        self.categoryData = {}
        self.extensionData = extensionData
        self.incomplete = incomplete
        self.grade_status = grade_status
        # FIXME Parse extension data!
        if not extensionData:
            self.extensionData = {}
        if isinstance(self.extensionData, str):
            try:
                self.extensionData = json.loads(self.extensionData)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                print(exc)
                self.extensionData = {}
        self.secret = secret
    
    def is_for_grade(self):
        return self.grade_status == "GRD" and not self.incomplete
    
    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "<Name: {}, SID: {}, Email: {}, Secret: {}, Total Points: {}>".format(self.name, self.sid, self.email, self.secret, str(self.total_points()))

    def is_auth(self, sid: str, secret: str) -> bool:
        return str(sid) == self.sid and (self.secret == secret or self.secret is None)

    def add_assignment_data(self, data: StudentAssignmentData):
        cat = data.assignment.category.name
        if cat not in self.categoryData:
            self.categoryData[cat] = []
        self.categoryData[cat].append(data)
    
    def add_category_data(self, data: StudentCategoryData):
        self.categoryData[data.category.name] = data

    def total_points(self, with_hidden=False, c=None):
        ignore_categories = set([])
        if c is not None:
            ignore_categories = c.get_ignore_category()
        tp = 0
        for c in self.categoryData.values():
            if c.category.name in ignore_categories:
                continue
            tp += c.get_total_score(with_hidden=with_hidden)
        return tp

    def get_assignment_data(self, assignment: Assignment) -> Assignment:
        cat = self.categoryData.get(assignment.category.name)
        if cat is None:
            return None
        for a in cat:
            if a.assignment == assignment:
                return a
        return None

    def get_category_data(self, category: Category) -> Category:
        return self.categoryData.get(category.name)

    def get_total_points_with_class(self, c, with_hidden=False) -> float:
        return self.total_points(c=c, with_hidden=with_hidden) + (c.get_raw_additional_pts() * (c.get_total_possible(only_inputted=True) / c.get_total_possible()))

    def get_grade(self, c, score=None, with_hidden=False) -> str:
        if self.incomplete:
            return "I"
        if score is None:
            score = self.get_total_points_with_class(c, with_hidden=with_hidden)
        grade_bins = c.grade_bins
        b = grade_bins.in_bin(score)
        return b.id

    def get_approx_grade_id(self, c, score=None, with_hidden=False) -> str:
        if self.incomplete:
            return "I"
        if score is None:
            score = self.get_total_points_with_class(c, with_hidden=with_hidden)
        cur_score = score
        cur_max_score = c.get_total_possible(only_inputted=True)
        b = c.grade_bins.relative_bin(cur_score, cur_max_score)
        return b.id

    def get_approx_grade(self, c) -> str:
        cur_score = self.get_total_points_with_class(c)
        cur_max_score = c.get_total_possible(only_inputted=True)
        b = c.grade_bins.relative_bin(cur_score, cur_max_score)
        return f"You are on track for a(n) {b.id} based off of the {cur_max_score} points entered."

    def apply_extensions(self):
        for ext_cat_key, value in self.extensionData.items():
            cat = self.categoryData.get(ext_cat_key)
            if cat is None:
                continue
            for ext_assign, value in value.items():
                assign = cat.get_assignment_data(ext_assign)
                if assign is None:
                    continue
                assign.extension_time = value

    def apply_slip_days(self):
        for cat in self.categoryData.values():
            cat.apply_slip_days()

    def main_results_str(self, c, include_rank=False):
        if c.all_inputted():
            grade_info = self.get_grade(c)
        else:
            grade_info = self.get_approx_grade(c)
        rank_str = ""
        if include_rank:
            rank, total = c.get_student_ranking(self)
            rank_str = f"Rank: {rank} / {total}\n"
        return f"{c.get_welcome()}{c.get_comment()}SID: {self.sid}\nemail: {self.email}\n\nTotal Points: {self.get_total_points_with_class(c)} / {c.get_total_possible()}\n{rank_str}Grade: {grade_info}"

    def dump_data(self, results_file: str, data: dict) -> None:
        jsondata = json.dumps(data, ensure_ascii=False)
        with open(results_file, "w") as f:
            f.write(jsondata)

    def dump_str(self, c, class_dist: bool=False, class_stats: bool=False, include_rank=False):
        tests = []
        results = {
            "score":self.get_total_points_with_class(c),
            "tests":tests
        }
        tests.append({"name":"Total", "output": self.main_results_str(c, include_rank=include_rank)})
        if class_dist or class_stats:
            stats_str = ""
            if class_stats:
                stats_str += c.get_class_points_stats_str()
                stats_str += "\n"
            if class_dist:
                stats_str += c.get_class_statistics_str()
            tests.append({"name": "Class Stats", "output": stats_str})
        for cat in self.categoryData.values():
            if not cat.is_hidden():
                tests.append({
                    "name": cat.category.name,
                    "output": cat.get_str()
                })
        return results

    def dump_result(self, c, class_dist: bool=False, include_rank=False):
        results = self.dump_str(c, class_dist=class_dist, include_rank=include_rank)
        self.dump_data("/autograder/results/results.json", results)

    def get_raw_data(self, c, approx_grade: bool=False, with_hidden=True):
        score = self.get_total_points_with_class(c, with_hidden=with_hidden)
        data = {
            "name": self.name,
            "sid": self.sid,
            "email": self.email,
            "grade": self.get_approx_grade_id(c, score=score, with_hidden=with_hidden) if approx_grade else self.get_grade(c, with_hidden=with_hidden),
            "score": score,
            "Grading Basis": self.grade_status
        }
        for cat in self.categoryData.values():
            for assign in cat.assignments_data:
                data[f"{cat.category.name}/{assign.assignment.id}"] = assign.get_course_points()
        return data
        
                
from .assignment import Assignment, StudentAssignmentData
from .category import Category, StudentCategoryData
