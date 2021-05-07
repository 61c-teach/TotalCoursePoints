from .assignment import Assignment, StudentAssignmentData
from .student import Student
from typing import List, Callable
class Group(Assignment):
    """
    This class will allow you to group together different assignments in one assignment.
    
    Score merger will take in all the Student Assignment Datas for a single student and generate a StudentAssignmentData from it.
    """

    def __init__(self, id: str, category, score_merger: Callable[[List[StudentAssignmentData]], StudentAssignmentData], assignments: List[Assignment]=[], *args, **kwargs):
        self.assignments = assignments
        self.score_merger = score_merger
        super().__init__(id, category, *args, **kwargs)

    def has_assignment(self, assignment: Assignment):
        return assignment not in self.assignments

    def add_assignment(self, assignment: Assignment):
        if self.has_assignment(assignment):
            raise ValueError(f"Group already contains the assignment: {assignment}")
        self.assignments.append(assignment)

    def load(self):
        tmp = f": {self.name}" if self.name is not None else ""
        load_str = f"Loading group {self.id}{tmp}..."
        load_str_done = load_str + "Done!"
        print(load_str)
        for assignment in self.assignments:
            assignment.load()
            self.data_loaded = self.data_loaded or assignment.data_loaded

        seen_students = set()

        for assignment in self.assignments:
            scores = assignment.data.values()
            for _score in scores:
                if not isinstance(_score, list):
                    _score = [_score]
                for score in _score:
                    student = (score.name, score.sid, score.email)
                    if student in seen_students:
                        continue
                    seen_students.add(student)
                    sid = student[1]
                    email = student[2]
                    std = Student(student[0], sid, email)
                    

                    asmts = []
                    group_msg = "Groupped Assignments:\n" + ("~" * 20) + "\n"
                    for a in self.assignments:
                        sad = a.get_student_data(std)
                        asmts.append(sad)
                        group_msg += sad.get_str().replace("*", ".").replace("-", "_")
                        group_msg += "\n" + ("~" * 20) + "\n"

                    new_sad = self.score_merger(asmts)
                    new_sad.assignment = self
                    self.all_scores.append(new_sad.score)
                    self.scores.append(new_sad.score)

                    if not isinstance(new_sad, StudentAssignmentData):
                        raise ValueError("Score merger function must return a StudentAssignmentData object")

                    new_sad.personal_comment = group_msg + new_sad.personal_comment

                    dat = self.data.get(sid)
                    if dat is None:
                        self.data[sid] = new_sad
                    else:
                        if isinstance(dat, list):
                            dat.append(new_sad)
                        else:
                            self.data[sid] = [dat, new_sad]
                    if sid in self.data:
                        if isinstance(self.data[sid], list):
                            self.data[sid].append(new_sad)

                    edat = self.edata.get(email)
                    if edat is None:
                        self.edata[email] = new_sad
                    else:
                        if isinstance(email, list):
                            edat.append(new_sad)
                        else:
                            self.edata[email] = [edat, new_sad]
                    if email in self.edata:
                        if isinstance(self.edata[email], list):
                            self.edata[email].append(new_sad)
        
        print(load_str_done)


