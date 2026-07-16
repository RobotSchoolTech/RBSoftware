'use client'

import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import * as academicService from '@/services/academic'
import type { User } from '@/lib/types'

interface Props {
  courseId: string
  courseName: string
  currentTeacherId: string
  onClose: () => void
  onChanged: () => void
}

export function ChangeTeacherModal({
  courseId,
  courseName,
  currentTeacherId,
  onClose,
  onChanged,
}: Props) {
  const [teacherId, setTeacherId] = useState(currentTeacherId)
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    academicService
      .listAssignableTeachers(courseId)
      .then(setUsers)
      .catch(() => setError('No se pudo cargar la lista de docentes'))
      .finally(() => setLoading(false))
  }, [courseId])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!teacherId || teacherId === currentTeacherId) return
    setSaving(true)
    setError(null)
    try {
      await academicService.assignCourseTeacher(courseId, teacherId)
      onChanged()
    } catch (err: any) {
      setError(err?.detail ?? 'Error al cambiar el docente')
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border bg-background p-6 shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Cambiar docente</h2>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
          >
            <X size={18} />
          </button>
        </div>

        <p className="text-sm text-muted-foreground mb-4">
          Curso: <span className="font-medium text-foreground">{courseName}</span>
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Docente</label>
            <select
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              value={teacherId}
              onChange={(e) => setTeacherId(e.target.value)}
              disabled={loading || saving}
              required
            >
              {users.map((u) => (
                <option key={u.public_id} value={u.public_id}>
                  {u.first_name} {u.last_name} — {u.email}
                  {u.public_id === currentTeacherId ? ' (actual)' : ''}
                </option>
              ))}
            </select>
            {loading && (
              <p className="mt-1 text-xs text-muted-foreground">Cargando docentes…</p>
            )}
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={saving || loading || !teacherId || teacherId === currentTeacherId}
            >
              {saving ? 'Guardando…' : 'Guardar'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
