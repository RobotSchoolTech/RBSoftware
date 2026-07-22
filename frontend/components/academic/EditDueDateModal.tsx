'use client'

import { useState } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DateTimePicker } from '@/components/ui/date-time-picker'
import * as academicService from '@/services/academic'
import type { AssignmentRead } from '@/lib/types'

interface Props {
  assignment: AssignmentRead
  onClose: () => void
  onSaved: () => void
}

/** Editar / ampliar la fecha límite de una actividad (usa el PATCH existente).
 *  Al ampliar la fecha, cambia qué entregas cuentan como tardías. */
export function EditDueDateModal({ assignment, onClose, onSaved }: Props) {
  const [dueDate, setDueDate] = useState<string | null>(assignment.due_date)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSave() {
    setError(null)
    setSaving(true)
    try {
      await academicService.updateAssignment(assignment.public_id, {
        due_date: dueDate,
      })
      onSaved()
    } catch (err: any) {
      setError(err?.detail ?? 'Error al actualizar la fecha')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-sm rounded-lg border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="font-semibold">Fecha límite</h3>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-muted">
            <X size={16} />
          </button>
        </div>
        <div className="space-y-3 px-5 py-4">
          <p className="text-sm text-muted-foreground">
            Ajusta la fecha límite de <span className="font-medium">{assignment.title}</span>.
            Las entregas posteriores a esta fecha se marcan como tardías.
          </p>
          <DateTimePicker value={dueDate} onChange={setDueDate} />
          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>
              Cancelar
            </Button>
            <Button size="sm" disabled={saving} onClick={handleSave}>
              {saving ? 'Guardando…' : 'Guardar'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
