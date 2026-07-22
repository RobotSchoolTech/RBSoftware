'use client'

import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/use-toast'
import { LOGROS, LOGRO_LABELS } from '@/lib/logros'
import * as academicService from '@/services/academic'
import type { AssignmentRead } from '@/lib/types'
import { CreateAssignmentModal } from './CreateAssignmentModal'
import { AssignmentDetailModal } from './AssignmentDetailModal'

interface Props {
  unitId: string
  assignments: AssignmentRead[]
  onChanged: () => void
  canEditContent?: boolean
}

export function AssignmentsTab({ unitId, assignments, onChanged, canEditContent = true }: Props) {
  const [showCreate, setShowCreate] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [toggling, setToggling] = useState<string | null>(null)
  const [savingLogro, setSavingLogro] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  async function handleDelete(id: string, title: string) {
    if (
      !window.confirm(
        `¿Borrar la tarea "${title}"? Esta acción no se puede deshacer.`,
      )
    ) {
      return
    }
    setDeleting(id)
    try {
      await academicService.deleteAssignment(id)
      toast({ title: 'Tarea eliminada', variant: 'success' })
      onChanged()
    } catch (err: any) {
      toast({
        title: err?.detail ?? 'No se pudo borrar la tarea',
        variant: 'destructive',
      })
    } finally {
      setDeleting(null)
    }
  }

  async function handleTogglePublish(id: string, isPublished: boolean) {
    setToggling(id)
    try {
      if (isPublished) {
        await academicService.unpublishAssignment(id)
      } else {
        await academicService.publishAssignment(id)
      }
      onChanged()
    } finally {
      setToggling(null)
    }
  }

  async function handleLogroChange(id: string, value: string) {
    setSavingLogro(id)
    try {
      await academicService.updateAssignment(id, { logro: value || null })
      onChanged()
    } finally {
      setSavingLogro(null)
    }
  }

  return (
    <>
      {showCreate && (
        <CreateAssignmentModal
          unitId={unitId}
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false)
            onChanged()
          }}
        />
      )}
      {selectedId && (
        <AssignmentDetailModal
          assignmentId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}

      <div className="space-y-2">
        {assignments.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Sin tareas
          </p>
        )}
        {assignments.map((a) => (
          <div
            key={a.public_id}
            className="flex items-center justify-between rounded-md border px-3 py-2 hover:bg-muted/30"
          >
            <div
              className="min-w-0 flex-1 cursor-pointer"
              onClick={() => setSelectedId(a.public_id)}
            >
              <p className="truncate text-sm font-medium">{a.title}</p>
              {a.due_date && (
                <p className="text-xs text-muted-foreground">
                  Límite: {new Date(a.due_date).toLocaleDateString()}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {canEditContent ? (
                <select
                  className="rounded-md border border-input bg-background px-2 py-1 text-xs"
                  value={a.logro ?? ''}
                  disabled={savingLogro === a.public_id}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => handleLogroChange(a.public_id, e.target.value)}
                >
                  <option value="">Sin logro</option>
                  {LOGROS.map((lg) => (
                    <option key={lg} value={lg}>
                      {LOGRO_LABELS[lg]}
                    </option>
                  ))}
                </select>
              ) : (
                a.logro && (
                  <Badge variant="secondary">
                    {LOGRO_LABELS[a.logro as keyof typeof LOGRO_LABELS] ?? a.logro}
                  </Badge>
                )
              )}
              <Badge variant={a.is_published ? 'success' : 'secondary'}>
                {a.is_published ? 'Publicada' : 'Borrador'}
              </Badge>
              <span className="text-xs text-muted-foreground">
                Máx: {a.max_score}
              </span>
              {canEditContent && (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={toggling === a.public_id}
                    onClick={() => handleTogglePublish(a.public_id, a.is_published)}
                  >
                    {a.is_published ? 'Despublicar' : 'Publicar'}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={deleting === a.public_id}
                    onClick={() => handleDelete(a.public_id, a.title)}
                  >
                    <Trash2 size={14} className="text-destructive" />
                  </Button>
                </>
              )}
            </div>
          </div>
        ))}
        {canEditContent && (
          <Button
            size="sm"
            variant="outline"
            className="w-full"
            onClick={() => setShowCreate(true)}
          >
            <Plus size={14} />
            <span className="ml-2">Nueva tarea</span>
          </Button>
        )}
      </div>
    </>
  )
}
