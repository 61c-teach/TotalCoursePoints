from __future__ import annotations
from .utils import GracePeriod, Time
import numpy as np

class Category:
    def __init__(self,
        name: str, 
        assignments = None, 
        course_points: float = None,
        late_penalty: float = 1,
        late_interval: Time = Time(days=1),
        blanket_late_penalty: bool = False,
        no_late_time: bool = False,
        max_slip_count: int = None,
        slip_interval: Time = Time(days=1),
        comment: str = "",
        show_stats: bool = True,
        show_rank: bool = True,
        out_of: float=None,
        grace_period: GracePeriod=None,
        hidden: bool=False,
        extra_credit: bool=False,
        drop_lowest_n_assignments: int=0,
        does_not_contribute: bool=False,
        max_late_time: int = None,
        percentage: bool = None,
        give_perfect_score: bool=False,
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
        self.no_late_time = no_late_time
        self.grace_period = grace_period
        self.hidden = hidden
        self.extra_credit = extra_credit
        self.drop_lowest_n_assignments = drop_lowest_n_assignments
        self.does_not_contribute = does_not_contribute
        self.max_late_time = None
        self.percentage = percentage
        self.give_perfect_score = give_perfect_score
        print(init_str_done)

    def add_assignments(self, assignments: list):
        for a in assignments:
            self.add_assignment(a)

    def add_assignment(self, assignment):
        self.assignments.append(assignment)

    def remove_assignment(self, assignment):
        if assignment in self.assignments:
            self.assignments.remove(assignment)

    def get_assignment(self, assign_name):
        for a in self.assignments:
            if a.id == assign_name:
                return a
        return None

    def load_assignment_data(self):
        for assignment in self.assignments:
            assignment.load_data()

    def get_total_possible(self, with_hidden=False, only_inputted=False):
        if self.extra_credit:
            return 0
        if self.course_points is not None:
            points = self.course_points
            if only_inputted:
                points = []
                for a in self.assignments:
                    if a.is_inputted(with_hidden=with_hidden) and not a.extra_credit:
                        points.append(a.get_total_possible())
                tot_a = len(self.assignments)
                cur_in = len(points)
                actual_amt = tot_a - self.drop_lowest_n_assignments
                points = [i for i in points if i != 0]
                if cur_in > actual_amt:
                    drop_n = cur_in - actual_amt
                    for i in range(min(drop_n, len(points))):
                        points.remove(min(points))
                points = sum(points)
            return points
        points = []
        for a in self.assignments:
            if (a.hidden and not with_hidden) or (not a.is_inputted() and only_inputted):
                continue
            points.append(a.get_total_possible())
        tot_a = len(self.assignments)
        cur_in = len(points)
        actual_amt = tot_a - self.drop_lowest_n_assignments
        points = [i for i in points if i != 0]
        if cur_in > actual_amt:
            drop_n = cur_in - actual_amt
            for i in range(drop_n):
                points.remove(min(points))
        points = sum(points)
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
    
    def gen_active_students_scores(self, c: "Classroom"):
        for a in self.assignments:
            a.gen_active_students_scores(c)


class StudentCategoryData:
    def __init__(self, category: Category, assignments: StudentAssignmentData=[]):
        self.category = category
        self.assignments_data: list(StudentAssignmentData) = assignments
        self.get_total_possible = category.get_total_possible
        self.reset_comment()
        self.override_score = None

    def append_comment(self, *args, sep=' ', end='\n'):
        self.personal_comment += sep.join(args) + end

    def reset_comment(self):
        self.personal_comment = ""
    
    def get_comment(self):
        c = self.personal_comment
        dla = self.category.drop_lowest_n_assignments
        if dla > 0:
            c = f"This category will drop your lowest {str(dla) + ' ' if dla != 1 else ''}assignment{'s' if dla != 1 else ''}.\n" + c
        return c

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "Category: {}\nAssignments:\n{}".format(self.category.name, self.assignments_data)

    def apply_optimal_slip_time(self, ignore_score=False):
        max_slip_count = self.category.max_slip_count
        if max_slip_count is None:
            return
        late_assignments = []
        for assignment in self.category.assignments:
            if isinstance(assignment.allowed_slip_count, int) and assignment.allowed_slip_count < 0:
                continue
            for assignment_data in self.assignments_data:
                if assignment_data.assignment == assignment:
                    if assignment_data.get_late_time().get_seconds() > 0 and (assignment_data.score > 0 or ignore_score):
                        late_assignments.append([assignment_data, assignment_data.get_num_late()])
                    break
        if len(late_assignments) == 0:
            return
        min_sd_to_use = 0
        possible_sd_per_assignment = []
        for la in late_assignments:
            possible_slip_day_usage = []
            if la[0].assignment.allowed_slip_count is not None: 
                la[1] = min(la[0].assignment.allowed_slip_count, la[1])
            min_sd_to_use += la[1]
            for i in range(la[1] + 1):
                possible_slip_day_usage.append(i)
            possible_sd_per_assignment.append(possible_slip_day_usage)
        choices = np.array(np.meshgrid(*possible_sd_per_assignment)).T.reshape(-1,len(possible_sd_per_assignment))
        combos = []
        min_slip_count = min(min_sd_to_use, max_slip_count)
        for c in choices:
            if min_slip_count <= sum(c) <= max_slip_count:
                combos.append(c)
        def assign_slip_days(assignments, times):
            for a, t in zip(assignments, times):
                a.slip_time_used = t
        aments = list(map(lambda x: x[0], late_assignments))
        possible_scores = []
        for combo in combos:
            assign_slip_days(aments, combo)
            possible_scores.append(self.get_total_score(with_hidden=True))
        best_combo_index = np.argmax(possible_scores)
        best_combo = combos[best_combo_index]
        assign_slip_days(aments, best_combo)
        # print(combos)
        # print(possible_scores)
        # print(best_combo)
        self.validate_slip_days()
    
    def validate_slip_days(self):
        mx = self.category.max_slip_count
        if mx is None:
            return
        count = 0
        for a in self.assignments_data:
            count += a.slip_time_used
            if count > mx:
                raise ValueError("Somehow applied more slipdays than the max!")

    def apply_ordered_slip_time(self, ignore_score=False):
        slip_time_left = self.category.max_slip_count
        if slip_time_left is None:
            return
        for assignment in self.category.assignments:
            if isinstance(assignment.allowed_slip_count, int) and assignment.allowed_slip_count < 0:
                continue
            for assignment_data in self.assignments_data:
                if assignment_data.assignment == assignment:
                    if assignment_data.get_late_time().get_seconds() > 0 and (assignment_data.score > 0 or ignore_score):
                        if assignment.allowed_slip_count is not None:
                            assignment_data.slip_time_used = min(assignment_data.get_num_late(), slip_time_left, assignment.allowed_slip_count)
                        else:
                            assignment_data.slip_time_used = min(assignment_data.get_num_late(), slip_time_left)
                        slip_time_left -= assignment_data.slip_time_used
                    break
        self.validate_slip_days()

    def drop_lowest_assignments(self):
        if self.category.drop_lowest_n_assignments >= len(self.assignments_data):
            raise ValueError("You cannot drop more assignments than what exists!")
        assignments = [(a, a.get_course_points()) for a in self.assignments_data if a.is_worth_points()]
        for i in range(self.category.drop_lowest_n_assignments):
            lowest = min(assignments, key=lambda x: x[1])
            lowest[0].drop_assignment()
            assignments.remove(lowest)

    def is_hidden(self):
        return self.category.hidden

    def get_assignment_data(self, assign_id: str) -> StudentAssignmentData:
        for assign in self.assignments_data:
            if assign.assignment.id == assign_id:
                return assign
        return None
    
    def all_inputted(self, with_hidden=False):
        return self.category.all_inputted(with_hidden=with_hidden)

    def get_str(self, score=None):
        s = "{}{}Here is the individual list of assignments:\n==========\n".format(self.category.comment, self.get_comment())
        slip_time_used = 0
        for assign in self.assignments_data:
            slip_time_used += assign.slip_time_used
            s += assign.get_str()
        if self.category.max_slip_count:
            s += "\nSlip time left: {} out of {}\n".format(self.category.max_slip_count - slip_time_used, self.category.max_slip_count)
        s += "\n++++++++++\nTotal points: {} / {}\n++++++++++".format(self.get_total_score(ignore_not_for_points=True) if score is None else score, self.category.get_total_possible())
        return s
    
    def get_total_score(self, with_hidden=False, ignore_not_for_points=False):
        if self.category.does_not_contribute and not ignore_not_for_points:
            return 0
        if self.override_score is not None:
            return self.override_score
        total = 0
        for a in self.assignments_data:
            if a.is_hidden() and not with_hidden:
                continue
            total += a.get_course_points()
        return total

    apply_slip_time = apply_ordered_slip_time


from .assignment import Assignment, StudentAssignmentData
from .student import Student
