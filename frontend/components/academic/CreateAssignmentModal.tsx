'use client'

import { useState } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DateTimePicker } from '@/components/ui/date-time-picker'
import { LOGROS, LOGRO_LABELS } from '@/lib/logros'
import * as academicService from '@/services/academic'

interface Props {
  unitId: string
  onClose: () => void
  onCreated: () => void
}

export function CreateAssignmentModal({ unitId, onClose, onCreated }: Props) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [dueDate, setDueDate] = useState<string | null>(null)
  const [maxScore, setMaxScore] = useState('100')
  const [logro, setLogro] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await academicService.createAssignment(unitId, {
        title: title.trim(),
        description: description.trim() || null,
        due_date: dueDate || null,
        max_score: parseInt(maxScore) || 100,
        logro: logro || null,
      })
      onCreated()
    } catch (err: any) {
      setError(err?.detail ?? 'Error al crear la tarea')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="font-semibold">Nueva tarea</h3>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-muted">
            <X size={16} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3 px-5 py-4">
          <div className="space-y-1">
            <label className="text-xs font-medium">Título *</label>
            <Input
              required
              placeholder="Título de la tarea"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium">Descripción</label>
            <textarea
              className="w-full min-h-[60px] rounded-md border border-input bg-background px-3 py-2 text-sm"
              placeholder="Instrucciones…"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium">Fecha límite</label>
              <DateTimePicker
                value={dueDate}
                onChange={setDueDate}
                disablePast
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">Puntaje máximo</label>
              <Input
                type="number"
                min="1"
                value={maxScore}
                onChange={(e) => setMaxScore(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium">Logro</label>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={logro}
              onChange={(e) => setLogro(e.target.value)}
            >
              <option value="">Sin logro</option>
              {LOGROS.map((lg) => (
                <option key={lg} value={lg}>
                  {LOGRO_LABELS[lg]}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              Define bajo qué logro (Diseñar, Programar o Robotizar) cuenta esta
              tarea en la planilla.
            </p>
          </div>
          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" size="sm" disabled={saving}>
              {saving ? 'Creando…' : 'Crear tarea'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
