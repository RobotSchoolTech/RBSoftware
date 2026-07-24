import { useEffect, useState } from 'react'
import * as academicService from '@/services/academic'
import type { CourseDetail, GradeWithCourses, User } from '@/lib/types'

export interface GradeCourseRow {
  public_id: string
  name: string
  teachers: User[]
  studentCount: number
  is_active: boolean
}

export interface GradeStudent {
  user: User
  courseName: string
  courseId: string
}

export function useGradeDetail(gradeId: string) {
  const [grade, setGrade] = useState<GradeWithCourses | null>(null)
  const [courseRows, setCourseRows] = useState<GradeCourseRow[]>([])
  const [students, setStudents] = useState<GradeStudent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const g = await academicService.getGrade(gradeId)
      setGrade(g)

      const details = await Promise.all(
        g.courses.map((c) =>
          academicService.getCourseDetail(c.public_id).catch(() => null),
        ),
      )

      const rows: GradeCourseRow[] = []
      const studs: GradeStudent[] = []

      for (const d of details) {
        if (!d) continue
        rows.push({
          public_id: d.public_id,
          name: d.name,
          teachers: d.teachers,
          studentCount: d.students.length,
          is_active: d.is_active,
        })
        for (const s of d.students) {
          studs.push({ user: s, courseName: d.name, courseId: d.public_id })
        }
      }

      setCourseRows(rows)
      setStudents(studs)
    } catch (err: any) {
      setError(err?.detail ?? 'Error al cargar grado')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [gradeId])

  return { grade, courseRows, students, loading, error, reload: load }
}
