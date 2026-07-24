'use client'

import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import type { CourseDetail } from '@/lib/types'
import { useStudentCourse } from '@/hooks/useStudentCourse'
import { StudentUnitSection } from './StudentUnitSection'

interface Props {
  course: CourseDetail
}

export function StudentCourseView({ course }: Props) {
  const router = useRouter()
  const { units, loading, error, reload } = useStudentCourse(course.public_id)

  const totalAssignments = units.reduce(
    (sum, u) => sum + u.assignments.length,
    0,
  )
  const submitted = units.reduce(
    (sum, u) =>
      sum + u.assignments.filter((a) => a.my_submission !== null).length,
    0,
  )
  const pct =
    totalAssignments > 0
      ? Math.round((submitted / totalAssignments) * 100)
      : 0

  return (
    <div className="space-y-6">
      <div>
        <button
          onClick={() => router.push('/academic/courses')}
          className="mb-2 flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft size={14} /> Mis Cursos
        </button>
        <h1 className="text-2xl font-semibold">{course.name}</h1>
        <p className="text-sm text-muted-foreground">
          {course.teachers.length > 1 ? 'Docentes' : 'Docente'}:{' '}
          {course.teachers.map((t) => `${t.first_name} ${t.last_name}`).join(', ') || '—'}
        </p>
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Progreso de tareas</span>
          <span className="font-medium">
            {submitted} de {totalAssignments} entregadas
          </span>
        </div>
        <div className="h-2 rounded-full bg-muted">
          <div
            className="h-2 rounded-full bg-primary transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {loading && (
        <p className="py-12 text-center text-muted-foreground">Cargando…</p>
      )}

      {!loading && error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center text-sm text-destructive">
          {error}
        </div>
      )}

      {!loading && !error && units.length === 0 && (
        <p className="py-12 text-center text-muted-foreground">
          No hay contenido publicado
        </p>
      )}

      {units.map((unit) => (
        <StudentUnitSection
          key={unit.public_id}
          unit={unit}
          onSubmitted={reload}
        />
      ))}
    </div>
  )
}
