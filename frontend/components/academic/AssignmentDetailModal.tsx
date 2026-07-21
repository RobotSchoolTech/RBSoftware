'use client'

import { useEffect, useState } from 'react'
import { Eye, Paperclip, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import * as academicService from '@/services/academic'
import type { SubmissionWithStudent } from '@/lib/types'
import { GradeSubmissionModal } from './GradeSubmissionModal'
import { FileViewerModal } from '@/components/file-viewer-modal'
import { RubricEditor } from '@/components/rubric-editor'

interface Props {
  assignmentId: string
  onClose: () => void
}

export function AssignmentDetailModal({ assignmentId, onClose }: Props) {
  const [submissions, setSubmissions] = useState<SubmissionWithStudent[]>([])
  const [loading, setLoading] = useState(true)
  const [gradingId, setGradingId] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [viewingSubmission, setViewingSubmission] = useState<{ id: string; name: string } | null>(null)

  async function load() {
    setLoading(true)
    try {
      setSubmissions(
        await academicService.getAssignmentSubmissions(assignmentId),
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [assignmentId])

  const gradingSub = submissions.find((s) => s.public_id === gradingId)

  return (
    <>
      <FileViewerModal
        isOpen={viewingSubmission !== null}
        onClose={() => setViewingSubmission(null)}
        submissionId={viewingSubmission?.id}
        fileName={viewingSubmission?.name ?? ''}
      />

      {gradingSub && (
        <GradeSubmissionModal
          submission={gradingSub}
          onClose={() => setGradingId(null)}
          onGraded={() => {
            setGradingId(null)
            load()
          }}
        />
      )}

      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="w-full max-w-3xl rounded-lg border bg-card shadow-xl">
          <div className="flex items-center justify-between border-b px-5 py-4">
            <h3 className="font-semibold">Entregas</h3>
            <button
              onClick={onClose}
              className="rounded-md p-1 hover:bg-muted"
            >
              <X size={16} />
            </button>
          </div>
          <div className="max-h-[70vh] overflow-y-auto px-5 py-4">
            <div className="mb-6">
              <h4 className="text-sm font-semibold mb-3">Rúbrica de evaluación</h4>
              <RubricEditor
                rubricEndpoint={`/academic/assignments/${assignmentId}/rubric`}
                canEdit={true}
              />
            </div>
            {loading && (
              <p className="py-8 text-center text-muted-foreground">
                Cargando…
              </p>
            )}
            {!loading && submissions.length === 0 && (
              <p className="py-8 text-center text-muted-foreground">
                Sin entregas
              </p>
            )}
            {!loading && submissions.length > 0 && (
              <div className="space-y-3">
                {submissions.map((s) => (
                  <div
                    key={s.public_id}
                    className="rounded-lg border"
                  >
                    <div className="flex items-center justify-between px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div>
                          <p className="text-sm font-medium">
                            {s.student.first_name} {s.student.last_name}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {s.student.email}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {s.file_name ? (
                          <Badge variant="outline" className="gap-1 border-green-300 text-green-700 dark:border-green-700 dark:text-green-400">
                            <Paperclip size={10} />
                            Con archivo
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-muted-foreground">
                            Solo texto
                          </Badge>
                        )}
                        {s.is_late && (
                          <Badge variant="destructive">Entregada tarde</Badge>
                        )}
                        <Badge
                          variant={
                            s.status === 'GRADED' ? 'success' : 'warning'
                          }
                        >
                          {s.status === 'GRADED' ? 'Calificado' : 'Entregado'}
                        </Badge>
                        {s.score !== null && (
                          <span className="text-sm font-medium">
                            {s.score} pts
                          </span>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {s.submitted_at
                            ? new Date(s.submitted_at).toLocaleDateString()
                            : '—'}
                        </span>
                      </div>
                    </div>

                    <div className="border-t px-4 py-3 space-y-2">
                      {s.content && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground mb-1">
                            Respuesta del estudiante:
                          </p>
                          <div className="rounded-md bg-muted/30 p-3 text-sm whitespace-pre-wrap">
                            {s.content}
                          </div>
                        </div>
                      )}

                      {s.file_name && (
                        <div className="flex items-center gap-2">
                          <p className="text-xs text-muted-foreground">
                            Archivo: {s.file_name}
                          </p>
                          <button
                            onClick={() => setViewingSubmission({ id: s.public_id, name: s.file_name! })}
                            className="flex items-center gap-1 text-xs text-primary hover:underline"
                          >
                            <Eye size={12} />
                            Ver archivo
                          </button>
                        </div>
                      )}

                      {!s.content && !s.file_name && (
                        <p className="text-xs text-muted-foreground italic">
                          Sin contenido adjunto
                        </p>
                      )}

                      {s.feedback && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground mb-1">
                            Retroalimentación:
                          </p>
                          <div className="rounded-md bg-green-50 dark:bg-green-900/10 p-3 text-sm">
                            {s.feedback}
                          </div>
                        </div>
                      )}

                      {s.status === 'SUBMITTED' && (
                        <div className="flex justify-end pt-1">
                          <Button
                            size="sm"
                            onClick={() => setGradingId(s.public_id)}
                          >
                            Calificar
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="flex justify-end border-t px-5 py-3">
            <Button variant="outline" size="sm" onClick={onClose}>
              Cerrar
            </Button>
          </div>
        </div>
      </div>
    </>
  )
}
