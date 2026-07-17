'use client'

import { useEffect, useState } from 'react'
import { Download, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  LOGROS,
  LOGRO_LABELS,
  NIVEL_CLASSES,
  nivelLabel,
  type Logro,
  type NivelLogro,
} from '@/lib/logros'
import * as academicService from '@/services/academic'
import type { Gradebook } from '@/lib/types'

interface Props {
  courseId: string
  courseName: string
}

function exportToCSV(gradebook: Gradebook) {
  const headers = [
    'Estudiante',
    'Email',
    ...LOGROS.map((lg) => LOGRO_LABELS[lg]),
    'Definitiva (%)',
    'Nivel general',
  ]
  const rows = gradebook.students.map((s) => [
    `${s.student.first_name} ${s.student.last_name}`,
    s.student.email,
    ...LOGROS.map((lg) => nivelLabel(s.logros[lg]?.level)),
    s.definitiva ?? '-',
    nivelLabel(s.definitiva_level),
  ])
  const csv = [headers, ...rows]
    .map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(','))
    .join('\n')
  // BOM UTF-8 para que Excel abra los acentos (Diseñar, etc.) correctamente.
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `planilla-${gradebook.course.name}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

function scoreColor(score: number | null | undefined, max: number) {
  if (score == null) return 'text-muted-foreground'
  const pct = (score / max) * 100
  return pct >= 60
    ? 'text-green-700 dark:text-green-400'
    : 'text-red-700 dark:text-red-400'
}

function round(n: number, d: number) {
  const f = 10 ** d
  return Math.round(n * f) / f
}

/** Badge de nivel cualitativo con su porcentaje. */
function LevelBadge({
  pct,
  level,
}: {
  pct: number | null
  level: string | null
}) {
  if (pct == null || !level) return <span className="text-muted-foreground">—</span>
  const cls = NIVEL_CLASSES[level as NivelLogro] ?? ''
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span
        className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}
      >
        {nivelLabel(level)}
      </span>
      <span className="text-[11px] text-muted-foreground">{pct}%</span>
    </div>
  )
}

export function GradebookTab({ courseId }: Props) {
  const [gradebook, setGradebook] = useState<Gradebook | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    academicService
      .getGradebook(courseId)
      .then(setGradebook)
      .catch((err: any) => setError(err?.detail ?? 'Error al cargar planilla'))
      .finally(() => setLoading(false))
  }, [courseId])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-muted-foreground">
        <Loader2 size={24} className="animate-spin mr-2" />
        Cargando planilla…
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center text-sm text-destructive m-4">
        {error}
      </div>
    )
  }

  if (!gradebook) return null

  const { assignments, students } = gradebook

  // Promedio de clase por logro (media de los promedios de los estudiantes con datos).
  const classLogro = (lg: Logro): number | null => {
    const vals = students
      .map((s) => s.logros[lg]?.average_pct)
      .filter((v): v is number => v != null)
    return vals.length ? round(vals.reduce((a, v) => a + v, 0) / vals.length, 1) : null
  }
  const classDefinitiva = (() => {
    const vals = students.map((s) => s.definitiva).filter((v): v is number => v != null)
    return vals.length ? round(vals.reduce((a, v) => a + v, 0) / vals.length, 1) : null
  })()

  const qualitative = (pct: number | null): string | null => {
    if (pct == null) return null
    if (pct >= 90) return 'excelente'
    if (pct >= 75) return 'bueno'
    if (pct >= 60) return 'regular'
    return 'insuficiente'
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between px-4 py-3 border-b">
        <h2 className="text-sm font-semibold">Planilla de calificaciones</h2>
        <Button variant="outline" size="sm" onClick={() => exportToCSV(gradebook)}>
          <Download size={14} />
          <span className="ml-1">Exportar CSV</span>
        </Button>
      </div>

      <div className="flex-1 overflow-auto">
        {assignments.length === 0 ? (
          <p className="py-20 text-center text-sm text-muted-foreground">
            No hay tareas creadas en este curso
          </p>
        ) : (
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-0 z-10 bg-background">
              <tr className="border-b">
                <th className="sticky left-0 z-20 bg-background text-left px-4 py-2 font-medium min-w-[180px]">
                  Estudiante
                </th>
                {assignments.map((a) => (
                  <th key={a.public_id} className="px-3 py-2 text-center font-medium min-w-[100px]">
                    <div className="truncate max-w-[120px] mx-auto" title={a.title}>
                      {a.title.length > 15 ? a.title.slice(0, 15) + '…' : a.title}
                    </div>
                    <div className="text-xs text-muted-foreground font-normal">/{a.max_score}</div>
                    <div className="text-[11px] font-normal text-primary">
                      {a.logro
                        ? LOGRO_LABELS[a.logro as Logro] ?? a.logro
                        : <span className="text-muted-foreground">Sin logro</span>}
                    </div>
                  </th>
                ))}
                {LOGROS.map((lg) => (
                  <th
                    key={lg}
                    className="px-3 py-2 text-center font-semibold min-w-[100px] border-l bg-muted/20"
                  >
                    {LOGRO_LABELS[lg]}
                  </th>
                ))}
                <th className="px-3 py-2 text-center font-semibold min-w-[100px] border-l bg-muted/40">
                  Definitiva
                </th>
              </tr>
            </thead>
            <tbody>
              {students.length === 0 ? (
                <tr>
                  <td
                    colSpan={assignments.length + LOGROS.length + 2}
                    className="py-8 text-center text-muted-foreground"
                  >
                    No hay estudiantes matriculados
                  </td>
                </tr>
              ) : (
                <>
                  {students.map((s) => (
                    <tr key={s.student.public_id} className="border-b hover:bg-muted/30">
                      <td className="sticky left-0 z-10 bg-background px-4 py-2">
                        <div className="font-medium">
                          {s.student.first_name} {s.student.last_name}
                        </div>
                        <div className="text-xs text-muted-foreground">{s.student.email}</div>
                      </td>
                      {assignments.map((a) => {
                        const g = s.grades[a.public_id]
                        return (
                          <td key={a.public_id} className="px-3 py-2 text-center">
                            {g == null ? (
                              <span className="text-muted-foreground">—</span>
                            ) : g.status === 'GRADED' && g.score != null ? (
                              <span className={scoreColor(g.score, a.max_score)}>
                                {g.score}/{a.max_score}
                              </span>
                            ) : g.status === 'SUBMITTED' ? (
                              <Badge variant="warning" className="text-xs">
                                Por calificar
                              </Badge>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </td>
                        )
                      })}
                      {LOGROS.map((lg) => {
                        const l = s.logros[lg]
                        return (
                          <td key={lg} className="px-3 py-2 text-center border-l bg-muted/10">
                            <LevelBadge pct={l?.average_pct ?? null} level={l?.level ?? null} />
                          </td>
                        )
                      })}
                      <td className="px-3 py-2 text-center border-l bg-muted/20">
                        <LevelBadge pct={s.definitiva} level={s.definitiva_level} />
                      </td>
                    </tr>
                  ))}
                  <tr className="border-t-2 bg-muted/20 font-medium">
                    <td className="sticky left-0 z-10 bg-muted/20 px-4 py-2">Promedio clase</td>
                    {assignments.map((a) => {
                      const scores = students
                        .map((s) => s.grades[a.public_id]?.score)
                        .filter((v): v is number => v != null)
                      const avg = scores.length
                        ? round(scores.reduce((acc, v) => acc + v, 0) / scores.length, 1)
                        : null
                      return (
                        <td key={a.public_id} className="px-3 py-2 text-center text-muted-foreground">
                          {avg != null ? avg : '—'}
                        </td>
                      )
                    })}
                    {LOGROS.map((lg) => {
                      const pct = classLogro(lg)
                      return (
                        <td key={lg} className="px-3 py-2 text-center border-l">
                          <LevelBadge pct={pct} level={qualitative(pct)} />
                        </td>
                      )
                    })}
                    <td className="px-3 py-2 text-center border-l">
                      <LevelBadge pct={classDefinitiva} level={qualitative(classDefinitiva)} />
                    </td>
                  </tr>
                </>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
