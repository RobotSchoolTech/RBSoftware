"""ACADEMIC domain SQLModel entities."""

from app.domains.academic.models.lms_assignment import LmsAssignment
from app.domains.academic.models.lms_course import LmsCourse
from app.domains.academic.models.lms_course_student import LmsCourseStudent
from app.domains.academic.models.lms_course_teacher import LmsCourseTeacher
from app.domains.academic.models.lms_grade import LmsGrade
from app.domains.academic.models.lms_grade_director import LmsGradeDirector
from app.domains.academic.models.lms_material import LmsMaterial
from app.domains.academic.models.lms_submission import LmsSubmission
from app.domains.academic.models.lms_unit import LmsUnit
from app.domains.academic.models.school import School
from app.domains.academic.models.pdf_annotation import PDFAnnotation
from app.domains.academic.models.rubric import Rubric
from app.domains.academic.models.rubric_criteria import RubricCriteria
from app.domains.academic.models.rubric_level import RubricLevel
from app.domains.academic.models.school_teacher import SchoolTeacher

__all__ = [
    "PDFAnnotation",
    "School",
    "SchoolTeacher",
    "LmsGrade",
    "LmsGradeDirector",
    "LmsCourse",
    "LmsCourseStudent",
    "LmsCourseTeacher",
    "LmsUnit",
    "LmsMaterial",
    "LmsAssignment",
    "LmsSubmission",
    "Rubric",
    "RubricCriteria",
    "RubricLevel",
]
