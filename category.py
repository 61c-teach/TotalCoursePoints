from __future__ import annotations
from .utils import GracePeriod, Time

class Category:
    def __init__(self,
        name: str, 
        assignments = None, 
        course_points: float = None,
        late_penalty: float = 1,
        late_interval: Time = Time(days=1),
        blanket_late_penalty: bool = False,
        max_slip_count: int = None,
        slip_interval: Time = Time(days=1),
        comment: str = "",
        show_stats: bool = True,
        show_rank: bool = True,
        out_of: float=None,
        grace_period: GracePeriod=None,
        hidden: bool=False
    ):
        init_str = f"Initializing category {name}..."
        init_str_done = init_str + "Done!"
        print(init_str)
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
        self.max_slip_count = max_slip_count
        self.slip_interval = slip_interval
        self.late_penalty = late_penalty
        self.late_interval = late_interval
        self.blanket_late_penalty = blanket_late_penalty
        self.grace_period = grace_period
        self.hidden = hidden
        print(init_str_done)

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

    def get_total_possible(self, with_hidden=False, only_inputted=False):
        if self.course_points is not None:
            points = self.course_points
            if only_inputted:
                points = 0
                for a in self.assignments:
                    if a.is_inputted(with_hidden=with_hidden):
                        points += a.get_total_possible()
            return points
        points = 0
        for a in self.assignments:
            if (a.hidden and not with_hidden) or (not a.is_inputted() and only_inputted):
                continue
            points += a.get_total_possible()
        return points
            
    def all_inputted(self, with_hidden=False):
        if self.hidden and not with_hidden:
            return True
        for a in self.assignments:
            if not a.is_inputted(with_hidden=with_hidden):
                return False
        return True

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
        self.reset_comment()

    def append_comment(self, *args, sep=' ', end='\n'):
        self.personal_comment += sep.join(args) + end

    def reset_comment(self):
        self.personal_comment = ""
    
    def get_comment(self):
        return self.personal_comment

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "Category: {}\nAssignments:\n{}".format(self.category.name, self.assignments_data)

    def apply_optimal_slip_time(self):
        pass

    def apply_ordered_slip_time(self):
        slip_time_left = self.category.max_slip_count
        if slip_time_left is None:
            return
        for assignment in self.category.assignments:
            if isinstance(assignment.allowed_slip_count, int) and assignment.allowed_slip_count < 0:
                continue
            for assignment_data in self.assignments_data:
                if assignment_data.assignment == assignment:
                    if assignment_data.get_late_time().get_seconds() > 0:
                        if assignment.allowed_slip_count is not None:
                            assignment_data.slip_time_used = min(assignment_data.get_num_late(), slip_time_left, assignment.allowed_slip_count)
                        else:
                            assignment_data.slip_time_used = min(assignment_data.get_num_late(), slip_time_left)
                        slip_time_left -= assignment_data.slip_time_used
                    continue

    def is_hidden(self):
        return self.category.hidden

    def get_assignment_data(self, assign_id: str) -> StudentAssignmentData:
        for assign in self.assignments_data:
            if assign.assignment.id == assign_id:
                return assign
        return None
    
    def all_inputted(self, with_hidden=False):
        return self.category.all_inputted(with_hidden=with_hidden)

    def get_str(self):
        s = "{}{}Here is the individual list of assignments:\n==========\n".format(self.category.comment, self.get_comment())
        slip_time_used = 0
        for assign in self.assignments_data:
            slip_time_used += assign.slip_time_used
            s += assign.get_str()
        if self.category.max_slip_count:
            s += "\nSlip time left: {} out of {}\n".format(self.category.max_slip_count - slip_time_used, self.category.max_slip_count)
        s += "\n++++++++++\nTotal points: {} / {}\n++++++++++".format(self.get_total_score(), self.category.get_total_possible())
        return s
    
    def get_total_score(self, with_hidden=False):
        total = 0
        for a in self.assignments_data:
            if a.is_hidden() and not with_hidden:
                continue
            total += a.get_course_points()
        return total

    apply_slip_days = apply_ordered_slip_time


from .assignment import Assignment, StudentAssignmentData
from .student import Student
