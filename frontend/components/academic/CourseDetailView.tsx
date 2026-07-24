'use client'

import { useCourseDetail } from '@/hooks/useCourseDetail'
import { useAuthStore } from '@/lib/store'
import { TeacherCourseView } from './TeacherCourseView'
import { StudentCourseView } from './StudentCourseView'

interface Props {
  courseId: string
}

export function CourseDetailView({ courseId }: Props) {
  const { course, units, loading, error, reload } = useCourseDetail(courseId)
  const user = useAuthStore((s) => s.user)
  const { isAdmin, hasRole } = useAuthStore()

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-muted-foreground">
        Cargando…
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center text-sm text-destructive">
        {error}
      </div>
    )
  }

  if (!course) {
    return (
      <div className="flex items-center justify-center py-20 text-muted-foreground">
        Curso no encontrado
      </div>
    )
  }

  const isTeacher = course.teachers.some((t) => t.public_id === user?.public_id)
  const canManage = isTeacher || isAdmin() || hasRole('DIRECTOR')
  const canEditContent = isTeacher || isAdmin()
  // Agregar/quitar docentes del curso es ADMIN-only: coincide con el
  // require_roles("ADMIN") del backend (POST/DELETE .../teachers).
  const canManageTeachers = isAdmin()

  if (canManage) {
    return (
      <TeacherCourseView
        course={course}
        units={units}
        reload={reload}
        canEditContent={canEditContent}
        canManageTeachers={canManageTeachers}
      />
    )
  }

  return <StudentCourseView course={course} />
}
