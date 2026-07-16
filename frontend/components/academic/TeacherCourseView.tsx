'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import type { CourseDetail, UnitRead } from '@/lib/types'
import { UnitsSidebar } from './UnitsSidebar'
import { UnitDetailPanel } from './UnitDetailPanel'
import { CreateUnitModal } from './CreateUnitModal'
import { CourseStudentsTab } from './CourseStudentsTab'
import { GradebookTab } from './GradebookTab'
import { ChangeTeacherModal } from './ChangeTeacherModal'

interface Props {
  course: CourseDetail
  units: UnitRead[]
  reload: () => void
  canEditContent: boolean
  canChangeTeacher?: boolean
}

type CourseTab = 'content' | 'students' | 'gradebook'

export function TeacherCourseView({
  course,
  units,
  reload,
  canEditContent,
  canChangeTeacher = false,
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
  const [showChangeTeacher, setShowChangeTeacher] = useState(false)

  const selectedUnit = units.find((u) => u.public_id === selectedUnitId) ?? null

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

      {showChangeTeacher && (
        <ChangeTeacherModal
          courseId={course.public_id}
          courseName={course.name}
          currentTeacherId={course.teacher.public_id}
          onClose={() => setShowChangeTeacher(false)}
          onChanged={() => {
            setShowChangeTeacher(false)
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
          <p className="text-xs text-muted-foreground">
            Docente: {course.teacher.first_name} {course.teacher.last_name}
            {canChangeTeacher && (
              <button
                onClick={() => setShowChangeTeacher(true)}
                className="ml-1 font-medium text-primary hover:underline"
              >
                Cambiar
              </button>
            )}
            {' · '}
            {course.students.length} estudiantes
          </p>
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
