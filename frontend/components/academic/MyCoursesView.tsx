'use client'

import { useRouter } from 'next/navigation'
import {
  BookOpen,
  GraduationCap,
  RefreshCw,
  School,
  UserCheck,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useMyCourses } from '@/hooks/useMyCourses'

export function MyCoursesView() {
  const router = useRouter()
  const { courses, loading, error, reload } = useMyCourses()

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Mis Cursos</h1>
          <p className="text-sm text-muted-foreground">
            {courses.length} curso{courses.length !== 1 && 's'} asignado
            {courses.length !== 1 && 's'}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          <span className="ml-2">Actualizar</span>
        </Button>
      </div>

      {loading && (
        <p className="py-12 text-center text-muted-foreground">Cargando…</p>
      )}

      {!loading && error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center text-sm text-destructive">
          {error}
        </div>
      )}

      {!loading && !error && courses.length === 0 && (
        <p className="py-12 text-center text-muted-foreground">
          No tienes cursos asignados
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {courses.map((c) => (
          <div
            key={c.public_id}
            onClick={() => router.push(`/academic/courses/${c.public_id}`)}
            className="cursor-pointer rounded-lg border bg-card p-4 transition-colors hover:bg-muted/30"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BookOpen size={16} className="text-muted-foreground" />
                <h3 className="font-medium">{c.name}</h3>
              </div>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  c.role === 'TEACHER'
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                    : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                }`}
              >
                {c.role === 'TEACHER' ? 'Docente' : 'Estudiante'}
              </span>
            </div>

            <div className="mt-2 space-y-1 text-sm text-muted-foreground">
              <div className="flex items-center gap-1.5">
                <GraduationCap size={13} />
                <span>{c.grade_name}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <School size={13} />
                <span>{c.school_name}</span>
              </div>
              {c.role === 'STUDENT' && (
                <div className="flex items-center gap-1.5">
                  <UserCheck size={13} />
                  <span>{c.teacher_names.join(', ') || '—'}</span>
                </div>
              )}
            </div>

            {c.description && (
              <p className="mt-2 text-sm text-muted-foreground line-clamp-2">
                {c.description}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
