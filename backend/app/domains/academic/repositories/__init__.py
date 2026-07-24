"""ACADEMIC domain repositories."""

from app.domains.academic.repositories.assignment_repository import AssignmentRepository
from app.domains.academic.repositories.course_repository import CourseRepository
from app.domains.academic.repositories.course_student_repository import CourseStudentRepository
from app.domains.academic.repositories.course_teacher_repository import CourseTeacherRepository
from app.domains.academic.repositories.grade_director_repository import GradeDirectorRepository
from app.domains.academic.repositories.grade_repository import GradeRepository
from app.domains.academic.repositories.material_repository import MaterialRepository
from app.domains.academic.repositories.pdf_annotation_repository import PDFAnnotationRepository
from app.domains.academic.repositories.rubric_repository import RubricRepository
from app.domains.academic.repositories.school_repository import SchoolRepository
from app.domains.academic.repositories.school_teacher_repository import SchoolTeacherRepository
from app.domains.academic.repositories.submission_repository import SubmissionRepository
from app.domains.academic.repositories.unit_repository import UnitRepository

__all__ = [
    "SchoolRepository",
    "SchoolTeacherRepository",
    "GradeRepository",
    "GradeDirectorRepository",
    "CourseRepository",
    "CourseStudentRepository",
    "CourseTeacherRepository",
    "UnitRepository",
    "MaterialRepository",
    "PDFAnnotationRepository",
    "AssignmentRepository",
    "SubmissionRepository",
    "RubricRepository",
]
