"""
This is a class which will contain info about the current student.
"""
from __future__ import annotations
import json
from . import GradeBins

class Student:
    def __init__(self, name: str, sid: str, email: str, extensionData: dict={}, secret: str=None):
        self.name = name
        self.sid = str(sid)
        self.email = email
        self.categoryData = {}
        self.extensionData = extensionData
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

    def total_points(self, with_hidden=False):
        tp = 0
        for c in self.categoryData.values():
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

    def get_grade(self, grade_bins: GradeBins) -> str:
        b = grade_bins.in_bin(self.total_points())
        return b.id

    def apply_extensions(self):
        for ext_cat_key, value in self.extensionData.items():
            cat = self.categoryData.get(ext_cat_key)
            if cat is None:
                continue
            for ext_assign, value in value.items():
                assign = cat.get_assignment_data(ext_assign)
                if assign is None:
                    continue
                assign.extension_days = int(value)

    def apply_slip_days(self):
        for cat in self.categoryData.values():
            cat.apply_slip_days()

    def main_results_str(self, c):
        return "SID: {}\nemail: {}\n\nTotal Points: {} / {}\nGrade: {}".format(self.sid, self.email, self.total_points(), c.get_total_possible(), self.get_grade(c.grade_bins))

    def dump_data(self, results_file: str, data: dict) -> None:
        jsondata = json.dumps(data, ensure_ascii=False)
        with open(results_file, "w") as f:
            f.write(jsondata)

    def dump_result(self, c):
        tests = []
        results = {
            "score":self.total_points(),
            "tests":tests
        }
        tests.append({"name":"Total", "output": self.main_results_str(c)})
        for cat in self.categoryData.values():
            if not cat.is_hidden():
                tests.append({
                    "name": cat.category.name,
                    "output": cat.get_str()
                })
        self.dump_data("/autograder/results/results.json", results)
        
                
from .assignment import Assignment, StudentAssignmentData
from .category import Category, StudentCategoryData