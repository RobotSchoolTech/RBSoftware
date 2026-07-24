'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft, X } from 'lucide-react'
import type { CourseDetail, UnitRead } from '@/lib/types'
import * as academicService from '@/services/academic'
import { UnitsSidebar } from './UnitsSidebar'
import { UnitDetailPanel } from './UnitDetailPanel'
import { CreateUnitModal } from './CreateUnitModal'
import { CourseStudentsTab } from './CourseStudentsTab'
import { GradebookTab } from './GradebookTab'
import { AddTeacherModal } from './AddTeacherModal'

interface Props {
  course: CourseDetail
  units: UnitRead[]
  reload: () => void
  canEditContent: boolean
  canManageTeachers?: boolean
}

type CourseTab = 'content' | 'students' | 'gradebook'

export function TeacherCourseView({
  course,
  units,
  reload,
  canEditContent,
  canManageTeachers = false,
}: Props) {
  const router = useRouter()
  const [courseTab, setCourseTab] = useState<CourseTab>(() => {
    if (typeof window === 'undefined') return 'content'
    const t = new URLSearchParams(window.location.search).get('tab')
    if (t === 'students' || t === 'gradebook' || t === 'content') return t
    return 'content'
  })
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(
    units[0]?.public_id ?? null,
  )
  const [showCreateUnit, setShowCreateUnit] = useState(false)
  const [showAddTeacher, setShowAddTeacher] = useState(false)
  const [removingTeacherId, setRemovingTeacherId] = useState<string | null>(null)
  const [teacherError, setTeacherError] = useState<string | null>(null)

  const selectedUnit = units.find((u) => u.public_id === selectedUnitId) ?? null

  async function handleRemoveTeacher(userId: string) {
    setTeacherError(null)
    setRemovingTeacherId(userId)
    try {
      await academicService.removeTeacher(course.public_id, userId)
      reload()
    } catch (err: any) {
      setTeacherError(err?.detail ?? 'No se pudo quitar el docente')
    } finally {
      setRemovingTeacherId(null)
    }
  }

  const courseTabs: { key: CourseTab; label: string }[] = [
    { key: 'content', label: 'Contenido' },
    { key: 'students', label: `Estudiantes (${course.students.length})` },
    { key: 'gradebook', label: 'Planilla' },
  ]

  return (
    <>
      {showCreateUnit && (
        <CreateUnitModal
          courseId={course.public_id}
          onClose={() => setShowCreateUnit(false)}
          onCreated={() => {
            setShowCreateUnit(false)
            reload()
          }}
        />
      )}

      {showAddTeacher && (
        <AddTeacherModal
          courseId={course.public_id}
          courseName={course.name}
          onClose={() => setShowAddTeacher(false)}
          onAdded={() => {
            setShowAddTeacher(false)
            reload()
          }}
        />
      )}

      <div className="flex h-full flex-col">
        <div className="shrink-0 border-b px-4 py-3">
          <button
            onClick={() => router.push('/academic/courses')}
            className="mb-1 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft size={12} /> Mis Cursos
          </button>
          <h1 className="text-lg font-semibold">{course.name}</h1>
          <div className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
            <span>Docentes:</span>
            {course.teachers.map((t) => (
              <span
                key={t.public_id}
                className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5"
              >
                {t.first_name} {t.last_name}
                {canManageTeachers && (
                  <button
                    onClick={() => handleRemoveTeacher(t.public_id)}
                    disabled={removingTeacherId === t.public_id}
                    title="Quitar docente"
                    className="text-muted-foreground hover:text-destructive disabled:opacity-50"
                  >
                    <X size={11} />
                  </button>
                )}
              </span>
            ))}
            {canManageTeachers && (
              <button
                onClick={() => setShowAddTeacher(true)}
                className="font-medium text-primary hover:underline"
              >
                + Agregar
              </button>
            )}
            <span>· {course.students.length} estudiantes</span>
          </div>
          {teacherError && (
            <p className="mt-1 text-xs text-destructive">{teacherError}</p>
          )}
        </div>

        <div className="flex shrink-0 border-b px-4">
          {courseTabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setCourseTab(t.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 ${
                courseTab === t.key
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {courseTab === 'content' && (
          <div className="flex flex-1 overflow-hidden">
            <UnitsSidebar
              units={units}
              selectedId={selectedUnitId}
              onSelect={setSelectedUnitId}
              onCreateUnit={() => setShowCreateUnit(true)}
              canEditContent={canEditContent}
            />
            <UnitDetailPanel
              unit={selectedUnit}
              course={course}
              onUnitChanged={reload}
              canEditContent={canEditContent}
            />
          </div>
        )}

        {courseTab === 'students' && (
          <div className="flex-1 overflow-y-auto p-4">
            <CourseStudentsTab course={course} onStudentChanged={reload} />
          </div>
        )}

        {courseTab === 'gradebook' && (
          <div className="flex-1 overflow-hidden">
            <GradebookTab courseId={course.public_id} courseName={course.name} />
          </div>
        )}
      </div>
    </>
  )
}
