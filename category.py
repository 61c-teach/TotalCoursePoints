from __future__ import annotations

class Category:
    def __init__(self,
        name: str, 
        assignments = None, 
        course_points: float = None,
        late_penalty: float = 1,
        max_slip_days: int = None,
        comment: str = "",
        show_stats: bool = True,
        show_rank: bool = True,
        out_of: float=None, 
        hidden: bool=False
    ):
        self.name = name
        if assignments is None:
            assignments = []
        self.assignments = assignments
        self.course_points = course_points
        if out_of is not None:
            self.out_of = out_of
        else:
            self.out_of = self.course_points
        self.show_stats = show_stats
        self.show_rank = show_rank
        self.comment = comment
        self.max_slip_days = max_slip_days
        self.late_penalty = late_penalty
        self.hidden = hidden

    def add_assignments(self, assignments: list):
        for a in assignments:
            self.add_assignment(a)

    def add_assignment(self, assignment):
        self.assignments.append(assignment)

    def remove_assignment(self, assignment):
        if assignment in self.assignments:
            self.assignments.remove(assignment)

    def load_assignment_data(self):
        for assignment in self.assignments:
            assignment.load_data()

    def get_total_possible(self, with_hidden=False):
        if self.course_points is not None:
            return self.course_points
        points = 0
        for a in self.assignments:
            if a.hidden and not with_hidden:
                continue
            points += a.get_total_possible()
        return points
            

    def get_student_data(self, student: Student):
        a_data = []
        for a in self.assignments:
            a_data.append(a.get_student_data(student))
        return StudentCategoryData(self, a_data)


class StudentCategoryData:
    def __init__(self, category: Category, assignments: StudentAssignmentData=[]):
        self.category = category
        self.assignments_data: list(StudentAssignmentData) = assignments
        self.get_total_possible = category.get_total_possible

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "Category: {}\nAssignments:\n{}".format(self.category.name, self.assignments_data)

    def apply_optimal_slip_days(self):
        pass

    def apply_ordered_slip_days(self):
        slip_days_left = self.category.max_slip_days
        if slip_days_left is None:
            return
        for assignment in self.category.assignments:
            if isinstance(assignment.allowed_slip_days, int) and assignment.allowed_slip_days < 0:
                continue
            for assignment_data in self.assignments_data:
                if assignment_data.assignment == assignment:
                    if assignment_data.get_late_days():
                        if assignment.allowed_slip_days is not None:
                            assignment_data.slip_days_used = min(assignment_data.get_late_days(), slip_days_left, assignment.allowed_slip_days)
                        else:
                            assignment_data.slip_days_used = min(assignment_data.get_late_days(), slip_days_left)
                        slip_days_left -= assignment_data.slip_days_used
                    continue

    def is_hidden(self):
        return self.category.hidden

    def get_assignment_data(self, assign_id: str) -> StudentAssignmentData:
        for assign in self.assignments_data:
            if assign.assignment.id == assign_id:
                return assign
        return None

    def get_str(self):
        s = "{}Here is the individual list of assignments:\n==========\n".format(self.category.comment)
        slip_days_used = 0
        for assign in self.assignments_data:
            slip_days_used += assign.slip_days_used
            s += assign.get_str()
        if self.category.max_slip_days:
            s += "\nSlip days left: {} out of {}\n".format(self.category.max_slip_days - slip_days_used, self.category.max_slip_days)
        s += "\n++++++++++\nTotal points: {} / {}\n++++++++++".format(self.get_total_score(), self.category.get_total_possible())
        return s
    
    def get_total_score(self, with_hidden=False):
        total = 0
        for a in self.assignments_data:
            if a.is_hidden() and not with_hidden:
                continue
            total += a.get_course_points()
        return total

    apply_slip_days = apply_ordered_slip_days


from .assignment import Assignment, StudentAssignmentData
from .student import Student