'use client'

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { StudentAssignment } from '@/lib/types'
import { SubmitAssignmentModal } from './SubmitAssignmentModal'

interface Props {
  assignment: StudentAssignment
  onSubmitted: () => void
}

function statusBadge(sub: StudentAssignment['my_submission']) {
  if (!sub) return <Badge variant="destructive">Pendiente</Badge>
  if (sub.status === 'GRADED')
    return <Badge variant="success">Calificada</Badge>
  return <Badge variant="warning">Entregada</Badge>
}

export function StudentAssignmentItem({ assignment, onSubmitted }: Props) {
  const [showModal, setShowModal] = useState(false)
  const sub = assignment.my_submission

  return (
    <>
      {showModal && (
        <SubmitAssignmentModal
          assignment={assignment}
          submission={sub}
          onClose={() => setShowModal(false)}
          onSubmitted={() => {
            setShowModal(false)
            onSubmitted()
          }}
        />
      )}

      <div className="rounded-md border p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="min-w-0">
            <p className="text-sm font-medium">{assignment.title}</p>
            {assignment.due_date && (
              <p className="text-xs text-muted-foreground">
                Límite: {new Date(assignment.due_date).toLocaleDateString()}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {sub?.is_late && <Badge variant="destructive">Tarde</Badge>}
            {statusBadge(sub)}
            <span className="text-xs text-muted-foreground">
              /{assignment.max_score}
            </span>
          </div>
        </div>

        {assignment.description && (
          <p className="text-sm text-muted-foreground">
            {assignment.description}
          </p>
        )}

        {/* Graded card */}
        {sub?.status === 'GRADED' && (
          <div className="rounded-md bg-green-500/10 p-3 space-y-1">
            <p className="text-sm font-medium text-green-700">
              Puntaje: {sub.score}/{assignment.max_score}
            </p>
            {sub.feedback && (
              <p className="text-sm text-green-700">{sub.feedback}</p>
            )}
          </div>
        )}

        <Button
          size="sm"
          variant={sub ? 'outline' : 'default'}
          onClick={() => setShowModal(true)}
        >
          {!sub
            ? 'Entregar'
            : sub.status === 'GRADED'
              ? 'Ver entrega'
              : 'Ver / Actualizar'}
        </Button>
      </div>
    </>
  )
}
