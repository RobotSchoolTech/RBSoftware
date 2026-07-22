import { api } from '@/lib/api'
import type {
  AssignmentRead,
  CourseDetail,
  CourseRead,
  Gradebook,
  Grade,
  GradeWithCourses,
  MaterialRead,
  MyCourseRead,
  School,
  StudentUnitContent,
  SubmissionWithStudent,
  UnitRead,
  User,
} from '@/lib/types'

// ── Schools ──────────────────────────────────────────────────────────────────

export function listSchools() {
  return api.get<School[]>('/academic/schools')
}

export function getSchool(id: string) {
  return api.get<School>(`/academic/schools/${id}`)
}

export function createSchool(data: {
  name: string
  city?: string | null
  address?: string | null
  contact_name?: string | null
  contact_email?: string | null
  contact_phone?: string | null
  work_line?: string | null
}) {
  return api.post<School>('/academic/schools', data)
}

export function updateSchool(
  id: string,
  data: Partial<{
    name: string
    city: string | null
    address: string | null
    contact_name: string | null
    contact_email: string | null
    contact_phone: string | null
    work_line: string | null
  }>,
) {
  return api.patch<School>(`/academic/schools/${id}`, data)
}

// ── Grades ───────────────────────────────────────────────────────────────────

export function listGradesBySchool(schoolId: string) {
  return api.get<Grade[]>(`/academic/schools/${schoolId}/grades`)
}

export function getMyGrades() {
  return api.get<Grade[]>('/academic/my-grades')
}

export function getGrade(gradeId: string) {
  return api.get<GradeWithCourses>(`/academic/grades/${gradeId}`)
}

export function createGrade(
  schoolId: string,
  data: { name: string; description?: string | null },
) {
  return api.post<Grade>(
    `/academic/schools/${schoolId}/grades`,
    data,
  )
}

export function deleteGrade(gradeId: string) {
  return api.delete(`/academic/grades/${gradeId}`)
}

export function assignDirector(gradeId: string, userId: string) {
  return api.post(`/academic/grades/${gradeId}/director`, {
    user_id: userId,
  })
}

// ── Users (search) ───────────────────────────────────────────────────────────

export function listUsers() {
  return api.get<User[]>('/auth/users')
}

// ── School Teachers ──────────────────────────────────────────────────────────

export function listSchoolTeachers(schoolId: string) {
  return api.get<User[]>(`/academic/schools/${schoolId}/teachers`)
}

export function addSchoolTeacher(schoolId: string, userId: string) {
  return api.post(`/academic/schools/${schoolId}/teachers`, { user_id: userId })
}

export function removeSchoolTeacher(schoolId: string, userId: string) {
  return api.delete(`/academic/schools/${schoolId}/teachers/${userId}`)
}

// ── Courses ──────────────────────────────────────────────────────────────────

export function getMyCourses() {
  return api.get<MyCourseRead[]>('/academic/my-courses')
}

export function getCourseDetail(courseId: string) {
  return api.get<CourseDetail>(`/academic/courses/${courseId}`)
}

export function listCoursesByGrade(gradeId: string) {
  return api.get<CourseRead[]>(`/academic/grades/${gradeId}/courses`)
}

export function createCourse(
  gradeId: string,
  data: { name: string; description?: string | null; teacher_id: string },
) {
  return api.post<CourseRead>(`/academic/grades/${gradeId}/courses`, data)
}

export function listAssignableTeachers(courseId: string) {
  return api.get<User[]>(`/academic/courses/${courseId}/assignable-teachers`)
}

export function assignCourseTeacher(courseId: string, teacherId: string) {
  return api.post(`/academic/courses/${courseId}/teacher`, { teacher_id: teacherId })
}

export function getCourseStudents(courseId: string) {
  return api.get<User[]>(`/academic/courses/${courseId}/students`)
}

export function enrollStudent(courseId: string, userId: string) {
  return api.post(`/academic/courses/${courseId}/students`, { user_id: userId })
}

export function transferStudent(
  studentId: string,
  fromCourseId: string,
  toCourseId: string,
) {
  return api.post(`/academic/students/${studentId}/transfer`, {
    from_course_id: fromCourseId,
    to_course_id: toCourseId,
  })
}

// ── Units ────────────────────────────────────────────────────────────────────

export function listUnits(courseId: string) {
  return api.get<UnitRead[]>(`/academic/courses/${courseId}/units`)
}

export function createUnit(
  courseId: string,
  data: { title: string; description?: string | null },
) {
  return api.post<UnitRead>(`/academic/courses/${courseId}/units`, data)
}

export function updateUnit(
  unitId: string,
  data: Partial<{ title: string; description: string | null }>,
) {
  return api.patch<UnitRead>(`/academic/units/${unitId}`, data)
}

export function publishUnit(unitId: string) {
  return api.post(`/academic/units/${unitId}/publish`)
}

export function unpublishUnit(unitId: string) {
  return api.delete(`/academic/units/${unitId}/publish`)
}

// ── Materials ────────────────────────────────────────────────────────────────

export function listMaterials(unitId: string) {
  return api.get<MaterialRead[]>(`/academic/units/${unitId}/materials`)
}

export function deleteMaterial(materialId: string) {
  return api.delete(`/academic/materials/${materialId}`)
}

export function publishMaterial(materialId: string) {
  return api.post(`/academic/materials/${materialId}/publish`)
}

export function unpublishMaterial(materialId: string) {
  return api.delete(`/academic/materials/${materialId}/publish`)
}

export function viewMaterial(materialId: string) {
  return api.get<{ url: string }>(`/academic/materials/${materialId}/view`)
}

export function downloadMaterial(materialId: string) {
  return api.get<{ url: string }>(`/academic/materials/${materialId}/download`)
}

export function addMaterial(
  unitId: string,
  data: { title: string; type: string; content?: string | null },
  file?: File,
) {
  const form = new FormData()
  form.append('title', data.title)
  form.append('type', data.type)
  if (data.content) form.append('content', data.content)
  if (file) form.append('file', file)

  return api.postForm<MaterialRead>(
    `/academic/units/${unitId}/materials`,
    form,
  )
}

export function addMaterialFromRepository(
  unitId: string,
  data: { title: string; file_id: string },
) {
  return api.post<MaterialRead>(
    `/academic/units/${unitId}/materials/from-repository`,
    data,
  )
}

// ── Assignments ──────────────────────────────────────────────────────────────

export function listAssignments(unitId: string) {
  return api.get<AssignmentRead[]>(`/academic/units/${unitId}/assignments`)
}

export function createAssignment(
  unitId: string,
  data: {
    title: string
    description?: string | null
    due_date?: string | null
    max_score?: number
    logro?: string | null
  },
) {
  return api.post<AssignmentRead>(
    `/academic/units/${unitId}/assignments`,
    data,
  )
}

export function updateAssignment(
  assignmentId: string,
  data: {
    title?: string
    description?: string | null
    due_date?: string | null
    max_score?: number
    logro?: string | null
    is_published?: boolean
  },
) {
  return api.patch<AssignmentRead>(
    `/academic/assignments/${assignmentId}`,
    data,
  )
}

export function publishAssignment(assignmentId: string) {
  return api.post(`/academic/assignments/${assignmentId}/publish`)
}

export function unpublishAssignment(assignmentId: string) {
  return api.delete(`/academic/assignments/${assignmentId}/publish`)
}

export function deleteAssignment(assignmentId: string) {
  return api.delete(`/academic/assignments/${assignmentId}`)
}

export function getAssignmentSubmissions(assignmentId: string) {
  return api.get<SubmissionWithStudent[]>(
    `/academic/assignments/${assignmentId}/submissions`,
  )
}

// ── Grading ──────────────────────────────────────────────────────────────────

export function viewSubmission(submissionId: string) {
  return api.get<{ url: string; file_name: string }>(`/academic/submissions/${submissionId}/view`)
}

export function downloadSubmission(submissionId: string) {
  return api.get<{ url: string }>(`/academic/submissions/${submissionId}/download`)
}

export function gradeSubmission(
  submissionId: string,
  data: { score: number; feedback?: string | null },
) {
  return api.post(`/academic/submissions/${submissionId}/grade`, data)
}

// ── Gradebook ───────────────────────────────────────────────────────────────

export function getGradebook(courseId: string) {
  return api.get<Gradebook>(`/academic/courses/${courseId}/gradebook`)
}

// ── Student content ──────────────────────────────────────────────────────────

export function getStudentCourseContent(courseId: string) {
  return api.get<StudentUnitContent[]>(
    `/academic/courses/${courseId}/content`,
  )
}

export function submitAssignment(
  assignmentId: string,
  content?: string | null,
  file?: File,
) {
  const form = new FormData()
  if (content) form.append('content', content)
  if (file) form.append('file', file)

  return api.postForm(`/academic/assignments/${assignmentId}/submit`, form)
}
