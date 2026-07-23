'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  ArrowLeft,
  Award,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  ClipboardCheck,
  Download,
  Eye,
  EyeOff,
  FileText,
  Folder,
  Plus,
  Trash2,
  Upload,
  Video,
  X,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuthStore } from '@/lib/store'
import { api } from '@/lib/api'
import { toast } from '@/components/ui/use-toast'
import type { TrainingProgram, TrainingEnrollmentProgress } from '@/lib/types'
import type {
  TrainingModule,
  TrainingLesson,
  TrainingEvaluation,
  TrainingSubmission,
  QuizQuestion,
} from '@/services/training'
import * as trainingService from '@/services/training'
import { RubricEditor } from '@/components/rubric-editor'
import * as academicService from '@/services/academic'
import type { School, User } from '@/lib/types'

interface Props {
  program: TrainingProgram
  modules: TrainingModule[]
  reload: () => void
}

type ProgramTab = 'content' | 'resources' | 'enrolled' | 'gradebook' | 'practicals' | 'templates'

// ── Main component ──────────────────────────────────────────────────────────

export function AdminProgramView({ program, modules, reload }: Props) {
  const router = useRouter()
  const { isAdmin, hasRole } = useAuthStore()
  const [programTab, setProgramTab] = useState<ProgramTab>('content')
  const [templateUrl, setTemplateUrl] = useState<string | null>(null)
  const [uploadingTemplate, setUploadingTemplate] = useState(false)

  useEffect(() => {
    api
      .get<{ template_url: string | null }>(
        `/training/programs/${program.public_id}/certificate-template`,
      )
      .then((data) => setTemplateUrl(data.template_url))
      .catch(() => {})
  }, [program.public_id])

  const programTabs: { key: ProgramTab; label: string }[] = [
    { key: 'content', label: 'Contenido' },
    { key: 'resources', label: 'Recursos' },
    { key: 'enrolled', label: 'Inscritos' },
    { key: 'gradebook', label: 'Planilla' },
    { key: 'practicals', label: 'Entregas Prácticas' },
    { key: 'templates', label: 'Plantillas' },
  ]

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="shrink-0 border-b px-4 py-3">
        <button
          onClick={() => router.push('/training/programs')}
          className="mb-1 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft size={12} /> Programas
        </button>
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold">{program.name}</h1>
          <button
            onClick={async () => {
              await api.post(`/training/programs/${program.public_id}/publish`, {
                publish: !program.is_published,
              })
              reload()
            }}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              program.is_published
                ? 'bg-green-100 text-green-700 hover:bg-red-100 hover:text-red-700'
                : 'bg-gray-100 text-gray-500 hover:bg-green-100 hover:text-green-700'
            }`}
          >
            {program.is_published ? (
              <>
                <Eye size={12} />
                Publicado
              </>
            ) : (
              <>
                <EyeOff size={12} />
                Borrador
              </>
            )}
          </button>
        </div>
        {program.description && (
          <p className="text-xs text-muted-foreground">{program.description}</p>
        )}
      </div>

      {(isAdmin() || hasRole('SUPER_TRAINER')) && (
        <div className="flex items-center gap-3 p-4 rounded-xl border bg-card mx-4 mt-3">
          <div className="flex-1">
            <p className="text-sm font-medium">Plantilla del certificado</p>
            <p className="text-xs text-muted-foreground">
              {templateUrl
                ? 'Plantilla cargada — se usará como fondo del certificado'
                : 'Sin plantilla — se usará el badge predeterminado'}
            </p>
          </div>

          {templateUrl && (
            <img
              src={templateUrl}
              alt="Plantilla"
              className="h-16 w-24 object-cover rounded-lg border"
            />
          )}

          <label
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors ${
              uploadingTemplate
                ? 'bg-muted text-muted-foreground'
                : 'bg-primary text-white hover:bg-primary/90'
            }`}
          >
            {uploadingTemplate
              ? 'Subiendo...'
              : templateUrl
                ? 'Cambiar plantilla'
                : 'Subir plantilla'}
            <input
              type="file"
              accept="image/png,image/jpeg"
              className="hidden"
              disabled={uploadingTemplate}
              onChange={async (e) => {
                const file = e.target.files?.[0]
                if (!file) return
                setUploadingTemplate(true)
                try {
                  const formData = new FormData()
                  formData.append('file', file)
                  const result = await api.postForm<{ template_url: string }>(
                    `/training/programs/${program.public_id}/certificate-template`,
                    formData,
                  )
                  setTemplateUrl(result.template_url)
                  toast({ title: 'Plantilla actualizada', variant: 'success' })
                } catch {
                  toast({
                    title: 'Error al subir plantilla',
                    variant: 'destructive',
                  })
                } finally {
                  setUploadingTemplate(false)
                  e.target.value = ''
                }
              }}
            />
          </label>
        </div>
      )}

      {/* Program-level tabs */}
      <div className="flex shrink-0 border-b px-4">
        {programTabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setProgramTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${
              programTab === t.key
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {programTab === 'content' && (
        <ContentTab program={program} modules={modules} reload={reload} />
      )}
      {programTab === 'resources' && (
        <ResourcesTab program={program} canManage />
      )}
      {programTab === 'enrolled' && (
        <EnrolledTab program={program} />
      )}
      {programTab === 'gradebook' && (
        <GradebookTab programId={program.public_id} />
      )}
      {programTab === 'practicals' && (
        <PracticalsTab program={program} modules={modules} />
      )}
      {programTab === 'templates' && (
        <TemplatesTab program={program} />
      )}
    </div>
  )
}

// ── Content Tab (two-panel) ─────────────────────────────────────────────────

function ContentTab({ program, modules, reload }: Props) {
  const [selectedModuleId, setSelectedModuleId] = useState<string | null>(
    modules[0]?.public_id ?? null,
  )
  const [contentTab, setContentTab] = useState<'lessons' | 'evaluations'>('lessons')
  const [lessons, setLessons] = useState<TrainingLesson[]>([])
  const [evaluations, setEvaluations] = useState<TrainingEvaluation[]>([])
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [selectedEvalId, setSelectedEvalId] = useState<string | null>(null)
  const [showCreateModule, setShowCreateModule] = useState(false)
  const [showCreateLesson, setShowCreateLesson] = useState(false)
  const [showCreateEval, setShowCreateEval] = useState(false)
  const [showCreateQuestion, setShowCreateQuestion] = useState(false)

  const selectedModule = modules.find((m) => m.public_id === selectedModuleId) ?? null

  const [previewLesson, setPreviewLesson] = useState<{
    id: string
    title: string
    type: string
  } | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!selectedModuleId) return
    trainingService.listLessons(selectedModuleId).then(setLessons).catch(() => setLessons([]))
    trainingService.listEvaluations(selectedModuleId).then(setEvaluations).catch(() => setEvaluations([]))
    setSelectedEvalId(null)
    setQuestions([])
  }, [selectedModuleId])

  useEffect(() => {
    if (!selectedEvalId) { setQuestions([]); return }
    trainingService.listQuestions(selectedEvalId).then(setQuestions).catch(() => setQuestions([]))
  }, [selectedEvalId])

  function reloadModuleContent() {
    if (!selectedModuleId) return
    trainingService.listLessons(selectedModuleId).then(setLessons).catch(() => {})
    trainingService.listEvaluations(selectedModuleId).then(setEvaluations).catch(() => {})
  }

  async function toggleLesson(lessonId: string, publish: boolean) {
    await api.post(`/training/lessons/${lessonId}/publish`, { publish })
    reloadModuleContent()
  }

  async function moveLessonUp(lessonId: string) {
    if (!selectedModuleId) return
    const idx = lessons.findIndex((l) => l.public_id === lessonId)
    if (idx <= 0) return
    const newOrder = [...lessons]
    ;[newOrder[idx - 1], newOrder[idx]] = [newOrder[idx], newOrder[idx - 1]]
    await api.put(`/training/modules/${selectedModuleId}/lessons/reorder`, {
      lesson_ids: newOrder.map((l) => l.public_id),
    })
    reloadModuleContent()
  }

  async function moveLessonDown(lessonId: string) {
    if (!selectedModuleId) return
    const idx = lessons.findIndex((l) => l.public_id === lessonId)
    if (idx < 0 || idx >= lessons.length - 1) return
    const newOrder = [...lessons]
    ;[newOrder[idx], newOrder[idx + 1]] = [newOrder[idx + 1], newOrder[idx]]
    await api.put(`/training/modules/${selectedModuleId}/lessons/reorder`, {
      lesson_ids: newOrder.map((l) => l.public_id),
    })
    reloadModuleContent()
  }

  return (
    <>
      {showCreateModule && <CreateModuleModal programId={program.public_id} orderIndex={modules.length} onClose={() => setShowCreateModule(false)} onCreated={() => { setShowCreateModule(false); reload() }} />}
      {showCreateLesson && selectedModuleId && <CreateLessonModal moduleId={selectedModuleId} onClose={() => setShowCreateLesson(false)} onCreated={() => { setShowCreateLesson(false); reloadModuleContent() }} />}
      {showCreateEval && selectedModuleId && <CreateEvaluationModal moduleId={selectedModuleId} lessons={lessons} onClose={() => setShowCreateEval(false)} onCreated={() => { setShowCreateEval(false); reloadModuleContent() }} />}
      {showCreateQuestion && selectedEvalId && <CreateQuestionModal evaluationId={selectedEvalId} onClose={() => setShowCreateQuestion(false)} onCreated={() => { setShowCreateQuestion(false); trainingService.listQuestions(selectedEvalId).then(setQuestions) }} />}

      {previewLesson && previewUrl && (
        <div className="fixed inset-0 z-[200] bg-black/80 flex items-center justify-center p-4">
          <div className="bg-card rounded-xl shadow-2xl w-full max-w-4xl h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <div className="flex items-center gap-2">
                {previewLesson.type === 'PDF' ? (
                  <FileText size={18} className="text-red-500" />
                ) : (
                  <Video size={18} className="text-blue-500" />
                )}
                <span className="font-medium">{previewLesson.title}</span>
              </div>
              <button
                onClick={() => {
                  setPreviewLesson(null)
                  setPreviewUrl(null)
                }}
                className="p-2 rounded-lg hover:bg-muted"
              >
                <X size={18} />
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              {previewLesson.type === 'PDF' && (
                <iframe
                  src={`${previewUrl}#toolbar=0`}
                  className="w-full h-full border-0"
                  title={previewLesson.title}
                />
              )}
              {previewLesson.type === 'VIDEO' && (
                <video src={previewUrl} controls className="w-full h-full bg-black" />
              )}
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* Modules sidebar */}
        <div className="flex w-64 shrink-0 flex-col border-r bg-muted/20">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Módulos</p>
            <Button size="sm" variant="ghost" onClick={() => setShowCreateModule(true)}><Plus size={14} /></Button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {modules.length === 0 && <p className="px-3 py-6 text-center text-xs text-muted-foreground">Sin módulos</p>}
            {modules.map((m) => (
              <button key={m.public_id} onClick={() => { setSelectedModuleId(m.public_id); setContentTab('lessons') }}
                className={`w-full border-b px-3 py-3 text-left transition-colors ${selectedModuleId === m.public_id ? 'bg-primary/10 border-l-2 border-l-primary' : 'hover:bg-muted/40'}`}>
                <p className="truncate text-sm font-medium">{m.title}</p>
                <Badge variant={m.is_published ? 'success' : 'secondary'} className="mt-1 text-[10px]">{m.is_published ? 'Publicado' : 'Borrador'}</Badge>
              </button>
            ))}
          </div>
        </div>

        {/* Right panel */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {!selectedModule ? (
            <div className="flex flex-1 items-center justify-center text-muted-foreground">Selecciona un módulo</div>
          ) : (
            <>
              <div className="flex items-center justify-between border-b px-4 py-3">
                <div>
                  <h2 className="font-medium">{selectedModule.title}</h2>
                  {selectedModule.description && <p className="text-xs text-muted-foreground">{selectedModule.description}</p>}
                </div>
                {!selectedModule.is_published && (
                  <Button size="sm" variant="outline" onClick={async () => { await trainingService.publishModule(selectedModule.public_id); reload() }}>Publicar</Button>
                )}
              </div>
              <div className="flex shrink-0 border-b px-4">
                <button onClick={() => setContentTab('lessons')} className={`px-4 py-2 text-sm font-medium border-b-2 ${contentTab === 'lessons' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>
                  Lecciones ({lessons.length})
                </button>
                <button onClick={() => setContentTab('evaluations')} className={`px-4 py-2 text-sm font-medium border-b-2 ${contentTab === 'evaluations' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>
                  Evaluaciones ({evaluations.length})
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                {contentTab === 'lessons' && (
                  <div className="space-y-2">
                    <div className="flex justify-end"><Button size="sm" onClick={() => setShowCreateLesson(true)}><Plus size={14} className="mr-1" /> Nueva lección</Button></div>
                    {lessons.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">Sin lecciones</p>}
                    {lessons.map((l, i) => (
                      <div key={l.public_id} className="flex items-center justify-between rounded-lg border p-3">
                        <div className="flex items-center gap-3">
                          <div className="flex flex-col gap-0.5">
                            <button
                              onClick={() => moveLessonUp(l.public_id)}
                              disabled={i === 0}
                              className="p-0.5 rounded hover:bg-muted disabled:opacity-30"
                            >
                              <ChevronUp size={12} />
                            </button>
                            <button
                              onClick={() => moveLessonDown(l.public_id)}
                              disabled={i === lessons.length - 1}
                              className="p-0.5 rounded hover:bg-muted disabled:opacity-30"
                            >
                              <ChevronDown size={12} />
                            </button>
                          </div>
                          {l.type === 'PDF' && <FileText size={16} className="text-red-500" />}
                          {l.type === 'VIDEO' && <Video size={16} className="text-blue-500" />}
                          {l.type === 'TEXT' && <BookOpen size={16} className="text-muted-foreground" />}
                          <div>
                            <p className="text-sm font-medium">{l.title}</p>
                            <p className="text-xs text-muted-foreground">{l.type}{l.duration_minutes ? ` · ${l.duration_minutes} min` : ''}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {(l.type === 'PDF' || l.type === 'VIDEO') && (
                            <button
                              onClick={async () => {
                                const { url } = await trainingService.getLessonViewUrl(l.public_id)
                                setPreviewUrl(url)
                                setPreviewLesson({ id: l.public_id, title: l.title, type: l.type })
                              }}
                              className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                              title="Ver archivo"
                            >
                              <Eye size={14} />
                            </button>
                          )}
                          {l.is_published ? (
                            <button
                              onClick={() => toggleLesson(l.public_id, false)}
                              className="flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700 hover:bg-red-100 hover:text-red-700 transition-colors"
                            >
                              <Eye size={10} />
                              Publicada
                            </button>
                          ) : (
                            <button
                              onClick={() => toggleLesson(l.public_id, true)}
                              className="flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-500 hover:bg-green-100 hover:text-green-700 transition-colors"
                            >
                              <EyeOff size={10} />
                              Borrador
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {contentTab === 'evaluations' && (
                  <div className="space-y-2">
                    <div className="flex justify-end"><Button size="sm" onClick={() => setShowCreateEval(true)}><Plus size={14} className="mr-1" /> Nueva evaluación</Button></div>
                    {evaluations.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">Sin evaluaciones</p>}
                    {evaluations.map((ev) => (
                      <div key={ev.public_id}>
                        <div onClick={() => setSelectedEvalId(selectedEvalId === ev.public_id ? null : ev.public_id)}
                          className={`flex cursor-pointer items-center justify-between rounded-lg border p-3 transition-colors hover:bg-muted/30 ${selectedEvalId === ev.public_id ? 'border-primary bg-primary/5' : ''}`}>
                          <div className="flex items-center gap-3">
                            <ClipboardCheck size={16} className="text-muted-foreground" />
                            <div>
                              <p className="text-sm font-medium">{ev.title}</p>
                              <p className="text-xs text-muted-foreground">
                                {ev.type === 'QUIZ' ? 'Quiz' : 'Práctica'} · Aprueba con {ev.passing_score}/{ev.max_score}
                                {ev.after_lesson_public_id && (
                                  <>
                                    {' · '}
                                    Después de: {lessons.find((l) => l.public_id === ev.after_lesson_public_id)?.title ?? 'lección'}
                                  </>
                                )}
                              </p>
                            </div>
                          </div>
                          <button
                            onClick={async (e) => {
                              e.stopPropagation()
                              await api.post(`/training/evaluations/${ev.public_id}/publish`, {
                                publish: !ev.is_published,
                              })
                              reloadModuleContent()
                            }}
                            className={`flex items-center gap-1 px-2 py-1 rounded-full text-[10px] font-medium transition-colors ${
                              ev.is_published
                                ? 'bg-green-100 text-green-700 hover:bg-red-100 hover:text-red-700'
                                : 'bg-gray-100 text-gray-500 hover:bg-green-100 hover:text-green-700'
                            }`}
                          >
                            {ev.is_published ? 'Publicada' : 'Borrador'}
                          </button>
                        </div>
                        {selectedEvalId === ev.public_id && ev.type === 'QUIZ' && (
                          <div className="ml-6 mt-2 space-y-2 border-l-2 border-primary/20 pl-4">
                            <div className="flex items-center justify-between">
                              <p className="text-xs font-semibold uppercase text-muted-foreground">Preguntas ({questions.length})</p>
                              <Button size="sm" variant="outline" onClick={() => setShowCreateQuestion(true)}><Plus size={12} className="mr-1" /> Pregunta</Button>
                            </div>
                            {questions.map((q, i) => (
                              <div key={q.public_id} className="rounded-md border bg-card p-3">
                                <div className="flex items-start justify-between">
                                  <p className="text-sm"><span className="font-medium text-muted-foreground">{i + 1}.</span> {q.question}</p>
                                  <button className="ml-2 shrink-0 rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                                    onClick={async () => { await trainingService.deleteQuestion(q.public_id); trainingService.listQuestions(ev.public_id).then(setQuestions) }}>
                                    <Trash2 size={13} />
                                  </button>
                                </div>
                                <div className="mt-2 grid grid-cols-2 gap-1">
                                  {q.options.map((opt) => (
                                    <div key={opt.id} className={`rounded px-2 py-1 text-xs ${opt.id === q.correct_option ? 'bg-green-100 font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-muted text-muted-foreground'}`}>{opt.text}</div>
                                  ))}
                                </div>
                                <p className="mt-1 text-[10px] text-muted-foreground">{q.points} pts</p>
                              </div>
                            ))}
                          </div>
                        )}
                        {selectedEvalId === ev.public_id && (
                          <div className="ml-6 mt-2 border-l-2 border-primary/20 pl-4 pt-3">
                            <h4 className="text-sm font-semibold mb-3">Rúbrica de evaluación</h4>
                            <RubricEditor
                              rubricEndpoint={`/training/evaluations/${ev.public_id}/rubric`}
                              canEdit={true}
                            />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}

// ── Enrolled Tab ────────────────────────────────────────────────────────────

function EnrolledTab({ program }: { program: TrainingProgram }) {
  const { isAdmin, hasRole } = useAuthStore()
  const [progress, setProgress] = useState<TrainingEnrollmentProgress[]>([])
  const [loading, setLoading] = useState(true)
  const [showEnroll, setShowEnroll] = useState(false)

  useEffect(() => {
    trainingService.getProgramProgress(program.public_id).then((d) => { setProgress(d); setLoading(false) }).catch(() => setLoading(false))
  }, [program.public_id])

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {showEnroll && <EnrollTeacherModal programId={program.public_id} enrolledIds={progress.map((p) => p.user.public_id)} onClose={() => setShowEnroll(false)}
        onEnrolled={() => { setShowEnroll(false); trainingService.getProgramProgress(program.public_id).then(setProgress) }} />}

      <div className="flex justify-end mb-3">
        {(isAdmin() || hasRole('TRAINER')) && <Button size="sm" onClick={() => setShowEnroll(true)}><Plus size={14} className="mr-1" /> Inscribir docente</Button>}
      </div>

      {loading && <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>}
      {!loading && progress.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">Sin inscritos</p>}

      <div className="space-y-3">
        {progress.map((ep) => {
          const pct = ep.lessons_total > 0 ? Math.round((ep.lessons_completed / ep.lessons_total) * 100) : 0
          return (
            <div key={ep.enrollment_public_id} className="rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">{ep.user.first_name} {ep.user.last_name}</p>
                  <p className="text-xs text-muted-foreground">{ep.user.email}</p>
                </div>
                <div className="flex items-center gap-2">
                  {ep.is_eligible && ep.status !== 'COMPLETED' && isAdmin() && (
                    <Button size="sm" variant="outline" onClick={async () => {
                      try { await trainingService.issueCertificate(ep.enrollment_public_id); trainingService.getProgramProgress(program.public_id).then(setProgress) } catch {}
                    }}><CheckCircle2 size={13} className="mr-1" /> Emitir certificado</Button>
                  )}
                  <Badge variant={ep.status === 'COMPLETED' ? 'success' : 'secondary'}>{ep.status === 'COMPLETED' ? 'Completado' : 'Activo'}</Badge>
                </div>
              </div>
              <div className="mt-3">
                <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                  <span>Lecciones {ep.lessons_completed}/{ep.lessons_total}</span>
                  <span>Evaluaciones {ep.evaluations_passed}/{ep.evaluations_total}</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-blue-600 transition-all" style={{ width: `${pct}%` }} />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Gradebook Tab ───────────────────────────────────────────────────────────

interface GBEval { public_id: string; title: string; type: string; max_score: number; passing_score: number }
interface GBGrade { score: number; status: string; submission_id: string; type: string }
interface GBTeacher { teacher: { public_id: string; first_name: string; last_name: string; email: string }; grades: Record<string, GBGrade | null>; average: number | null; completed: number; total: number; is_certified: boolean }
interface GBData { program: { public_id: string; name: string }; evaluations: GBEval[]; teachers: GBTeacher[] }

function GradebookTab({ programId }: { programId: string }) {
  const [data, setData] = useState<GBData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get<GBData>(`/training/programs/${programId}/gradebook`).then((d) => { setData(d); setLoading(false) }).catch(() => setLoading(false))
  }, [programId])

  function exportCSV() {
    if (!data) return
    const headers = ['Docente', 'Email', ...data.evaluations.map((e) => e.title), 'Promedio', 'Certificado']
    const rows = data.teachers.map((t) => [
      `${t.teacher.first_name} ${t.teacher.last_name}`,
      t.teacher.email,
      ...data.evaluations.map((e) => { const g = t.grades[e.public_id]; return g ? `${g.score}/${e.max_score}` : '—' }),
      t.average !== null ? String(t.average) : '—',
      t.is_certified ? 'Si' : 'No',
    ])
    const csv = [headers, ...rows].map((r) => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `planilla-${data.program.name}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) return <div className="flex-1 p-4"><p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p></div>
  if (!data) return null

  return (
    <div className="flex-1 overflow-auto p-4">
      <div className="flex justify-end mb-3">
        <Button size="sm" variant="outline" onClick={exportCSV}><Download size={14} className="mr-1" /> Exportar CSV</Button>
      </div>
      {data.teachers.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Sin inscritos</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="sticky left-0 bg-muted/50 px-4 py-3 text-left font-medium">Docente</th>
                {data.evaluations.map((ev) => (
                  <th key={ev.public_id} className="px-4 py-3 text-center font-medium min-w-[120px]">
                    <div>{ev.title}</div>
                    <div className="text-[10px] font-normal text-muted-foreground">{ev.type === 'QUIZ' ? 'Quiz' : 'Práctica'} · {ev.passing_score}/{ev.max_score}</div>
                  </th>
                ))}
                <th className="px-4 py-3 text-center font-medium">Promedio</th>
                <th className="px-4 py-3 text-center font-medium">Cert.</th>
              </tr>
            </thead>
            <tbody>
              {data.teachers.map((t) => (
                <tr key={t.teacher.public_id} className="border-b hover:bg-muted/30">
                  <td className="sticky left-0 bg-card px-4 py-3">
                    <p className="font-medium">{t.teacher.first_name} {t.teacher.last_name}</p>
                    <p className="text-xs text-muted-foreground">{t.teacher.email}</p>
                  </td>
                  {data.evaluations.map((ev) => {
                    const g = t.grades[ev.public_id]
                    if (!g) return <td key={ev.public_id} className="px-4 py-3 text-center text-muted-foreground">—</td>
                    const passed = g.score >= ev.passing_score
                    return <td key={ev.public_id} className="px-4 py-3 text-center"><span className={`font-medium ${passed ? 'text-green-600' : 'text-red-600'}`}>{g.score}/{ev.max_score}</span></td>
                  })}
                  <td className="px-4 py-3 text-center">{t.average !== null ? <span className="font-semibold">{t.average}</span> : <span className="text-muted-foreground">—</span>}</td>
                  <td className="px-4 py-3 text-center">{t.is_certified ? <Award size={18} className="mx-auto text-green-600" /> : <span className="text-xs text-muted-foreground">{t.completed}/{t.total}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Practicals Tab ──────────────────────────────────────────────────────────

function PracticalsTab({ program, modules }: { program: TrainingProgram; modules: TrainingModule[] }) {
  const [allEvals, setAllEvals] = useState<TrainingEvaluation[]>([])
  const [selectedEvalId, setSelectedEvalId] = useState<string | null>(null)
  const [submissions, setSubmissions] = useState<TrainingSubmission[]>([])
  const [loading, setLoading] = useState(true)
  const [showGrade, setShowGrade] = useState<TrainingSubmission | null>(null)
  const [gradeEval, setGradeEval] = useState<TrainingEvaluation | null>(null)

  useEffect(() => {
    async function load() {
      const practicals: TrainingEvaluation[] = []
      for (const mod of modules) {
        const evals = await trainingService.listEvaluations(mod.public_id)
        practicals.push(...evals.filter((e) => e.type === 'PRACTICAL'))
      }
      setAllEvals(practicals)
      if (practicals.length > 0) {
        setSelectedEvalId(practicals[0].public_id)
      }
      setLoading(false)
    }
    load()
  }, [modules])

  useEffect(() => {
    if (!selectedEvalId) return
    trainingService.listSubmissions(selectedEvalId).then(setSubmissions).catch(() => setSubmissions([]))
  }, [selectedEvalId])

  const selectedEval = allEvals.find((e) => e.public_id === selectedEvalId) ?? null

  if (loading) return <div className="flex-1 p-4"><p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p></div>
  if (allEvals.length === 0) return <div className="flex-1 p-4"><p className="py-6 text-center text-sm text-muted-foreground">No hay evaluaciones prácticas</p></div>

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {showGrade && gradeEval && (
        <GradeModal
          submission={showGrade}
          evaluation={gradeEval}
          onClose={() => setShowGrade(null)}
          onGraded={() => {
            setShowGrade(null)
            if (selectedEvalId) trainingService.listSubmissions(selectedEvalId).then(setSubmissions)
          }}
        />
      )}

      <div className="mb-4">
        <label className="text-xs font-medium text-muted-foreground">Evaluación</label>
        <select
          className="mt-1 flex h-9 w-full max-w-md rounded-md border border-input bg-background px-3 text-sm"
          value={selectedEvalId ?? ''}
          onChange={(e) => setSelectedEvalId(e.target.value)}
        >
          {allEvals.map((ev) => (
            <option key={ev.public_id} value={ev.public_id}>{ev.title} ({ev.passing_score}/{ev.max_score})</option>
          ))}
        </select>
      </div>

      {submissions.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Sin entregas</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium">Entrega</th>
                <th className="px-4 py-3 text-center font-medium">Estado</th>
                <th className="px-4 py-3 text-center font-medium">Score</th>
                <th className="px-4 py-3 text-center font-medium">Archivo</th>
                <th className="px-4 py-3 text-center font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {submissions.map((sub) => (
                <tr key={sub.public_id} className="border-b hover:bg-muted/30">
                  <td className="px-4 py-3">
                    <p className="text-xs text-muted-foreground">{sub.submitted_at ? new Date(sub.submitted_at).toLocaleDateString('es-CO') : '—'}</p>
                    {sub.content && <p className="text-xs text-muted-foreground line-clamp-1 max-w-[200px]">{sub.content}</p>}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Badge variant={sub.status === 'GRADED' ? 'success' : sub.status === 'SUBMITTED' ? 'warning' : 'secondary'}>
                      {sub.status === 'GRADED' ? 'Calificada' : sub.status === 'SUBMITTED' ? 'Pendiente' : sub.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {sub.score !== null ? (
                      <span className={`font-medium ${selectedEval && sub.score >= selectedEval.passing_score ? 'text-green-600' : 'text-red-600'}`}>
                        {sub.score}/{selectedEval?.max_score}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {sub.file_name ? <span className="text-xs text-muted-foreground">{sub.file_name}</span> : '—'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {sub.status === 'SUBMITTED' && selectedEval && (
                      <Button size="sm" variant="outline" onClick={() => { setGradeEval(selectedEval); setShowGrade(sub) }}>Calificar</Button>
                    )}
                    {sub.status === 'GRADED' && sub.feedback && (
                      <span className="text-xs text-muted-foreground" title={sub.feedback}>Feedback enviado</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Grade Modal ─────────────────────────────────────────────────────────────

function GradeModal({ submission, evaluation, onClose, onGraded }: {
  submission: TrainingSubmission; evaluation: TrainingEvaluation; onClose: () => void; onGraded: () => void
}) {
  const [score, setScore] = useState('')
  const [feedback, setFeedback] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="font-semibold">Calificar entrega</h3>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X size={16} /></button>
        </div>
        <form onSubmit={async (e) => {
          e.preventDefault(); setError(null); setSaving(true)
          try {
            await trainingService.gradeSubmission(submission.public_id, {
              score: parseInt(score, 10),
              feedback: feedback.trim() || null,
            })
            onGraded()
          } catch (err: any) { setError(err?.detail ?? 'Error al calificar') }
          finally { setSaving(false) }
        }} className="space-y-3 px-5 py-4">
          {submission.content && (
            <div className="space-y-1">
              <label className="text-xs font-medium">Respuesta del docente</label>
              <div className="rounded-md bg-muted/50 p-3 text-sm text-muted-foreground max-h-32 overflow-y-auto">{submission.content}</div>
            </div>
          )}
          <div className="space-y-1">
            <label className="text-xs font-medium">Puntaje (0-{evaluation.max_score}) *</label>
            <Input required type="number" min={0} max={evaluation.max_score} placeholder={`Máx. ${evaluation.max_score}`} value={score} onChange={(e) => setScore(e.target.value)} />
            <p className="text-[10px] text-muted-foreground">Aprueba con {evaluation.passing_score}</p>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium">Retroalimentación</label>
            <textarea className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="Comentarios para el docente…" value={feedback} onChange={(e) => setFeedback(e.target.value)} />
          </div>
          {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>Cancelar</Button>
            <Button type="submit" size="sm" disabled={saving}>{saving ? 'Calificando…' : 'Calificar'}</Button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Inline Modals (unchanged) ───────────────────────────────────────────────

function CreateModuleModal({ programId, orderIndex, onClose, onCreated }: {
  programId: string; orderIndex: number; onClose: () => void; onCreated: () => void
}) {
  const [title, setTitle] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-sm rounded-lg border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="font-semibold">Nuevo módulo</h3>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X size={16} /></button>
        </div>
        <form onSubmit={async (e) => {
          e.preventDefault(); setError(null); setSaving(true)
          try { await trainingService.createModule(programId, { title: title.trim(), order_index: orderIndex }); onCreated() }
          catch (err: any) { setError(err?.detail ?? 'Error') } finally { setSaving(false) }
        }} className="space-y-3 px-5 py-4">
          <div className="space-y-1"><label className="text-xs font-medium">Título *</label>
            <Input required placeholder="Nombre del módulo" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
          {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>Cancelar</Button>
            <Button type="submit" size="sm" disabled={saving}>{saving ? 'Creando…' : 'Crear'}</Button></div>
        </form></div></div>
  )
}

function CreateLessonModal({ moduleId, onClose, onCreated }: {
  moduleId: string; onClose: () => void; onCreated: () => void
}) {
  const [form, setForm] = useState({ title: '', type: 'TEXT', content: '', duration_minutes: '' })
  const [file, setFile] = useState<File | null>(null)
  const [videoMode, setVideoMode] = useState<'url' | 'file'>('url')
  const [videoUrl, setVideoUrl] = useState('')
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [sourceMode, setSourceMode] = useState<'upload' | 'repository'>('upload')
  const [repoFile, setRepoFile] = useState<RepoFile | null>(null)
  const [showRepoPicker, setShowRepoPicker] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="font-semibold">Nueva lección</h3>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X size={16} /></button></div>
        <form onSubmit={async (e) => {
          e.preventDefault(); setError(null); setSaving(true)
          try {
            const useRepo =
              sourceMode === 'repository' &&
              repoFile &&
              (form.type === 'PDF' || (form.type === 'VIDEO' && videoMode === 'file'))
            if (useRepo && repoFile) {
              await trainingService.createLessonFromRepository(moduleId, {
                title: form.title.trim(),
                type: form.type as 'PDF' | 'VIDEO',
                file_id: repoFile.public_id,
                duration_minutes: form.duration_minutes ? Number(form.duration_minutes) : null,
              })
            } else {
              const fd = new FormData()
              fd.append('title', form.title.trim())
              fd.append('type', form.type)
              if (form.duration_minutes) fd.append('duration_minutes', form.duration_minutes)
              if (form.type === 'TEXT' && form.content.trim()) {
                fd.append('content', form.content.trim())
              } else if (form.type === 'PDF' && file) {
                fd.append('file', file)
              } else if (form.type === 'VIDEO') {
                if (videoMode === 'url' && videoUrl.trim()) {
                  fd.append('content', videoUrl.trim())
                } else if (videoMode === 'file' && videoFile) {
                  fd.append('file', videoFile)
                }
              }
              await trainingService.createLesson(moduleId, fd)
            }
            onCreated()
          } catch (err: any) { setError(err?.detail ?? 'Error') } finally { setSaving(false) }
        }} className="space-y-3 px-5 py-4">
          <div className="space-y-1"><label className="text-xs font-medium">Título *</label>
            <Input required placeholder="Título" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1"><label className="text-xs font-medium">Tipo *</label>
              <select className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                <option value="TEXT">Texto</option><option value="PDF">PDF</option><option value="VIDEO">Video</option></select></div>
            <div className="space-y-1"><label className="text-xs font-medium">Duración (min)</label>
              <Input type="number" min={1} placeholder="30" value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })} /></div></div>
          {form.type === 'TEXT' && <div className="space-y-1"><label className="text-xs font-medium">Contenido</label>
            <textarea className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} /></div>}
          {form.type === 'PDF' && (
            <div className="space-y-3">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setSourceMode('upload')}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    sourceMode === 'upload'
                      ? 'bg-primary text-white border-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  ↑ Subir archivo
                </button>
                <button
                  type="button"
                  onClick={() => setSourceMode('repository')}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    sourceMode === 'repository'
                      ? 'bg-primary text-white border-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  📁 Del repositorio
                </button>
              </div>
              {sourceMode === 'upload' && (
                <input type="file" accept=".pdf"
                  className="block w-full text-sm text-muted-foreground file:mr-2 file:rounded file:border-0 file:bg-muted file:px-3 file:py-1.5 file:text-sm file:font-medium"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              )}
              {sourceMode === 'repository' && (
                <RepoFilePickerField repoFile={repoFile}
                  onPick={() => setShowRepoPicker(true)}
                  onClear={() => setRepoFile(null)} />
              )}
            </div>
          )}
          {form.type === 'VIDEO' && (
            <div className="space-y-3">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setVideoMode('url')}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    videoMode === 'url'
                      ? 'bg-primary text-white border-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  🔗 Link
                </button>
                <button
                  type="button"
                  onClick={() => { setVideoMode('file'); setSourceMode('upload') }}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    videoMode === 'file' && sourceMode === 'upload'
                      ? 'bg-primary text-white border-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  ↑ Subir
                </button>
                <button
                  type="button"
                  onClick={() => { setVideoMode('file'); setSourceMode('repository') }}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    videoMode === 'file' && sourceMode === 'repository'
                      ? 'bg-primary text-white border-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  📁 Repositorio
                </button>
              </div>
              {videoMode === 'url' && (
                <div className="space-y-1">
                  <label className="text-xs font-medium">URL del video</label>
                  <input
                    type="url"
                    placeholder="https://youtube.com/watch?v=..."
                    value={videoUrl}
                    onChange={(e) => setVideoUrl(e.target.value)}
                    className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                  />
                  <p className="text-xs text-muted-foreground">Soporta YouTube, Vimeo y otros</p>
                </div>
              )}
              {videoMode === 'file' && sourceMode === 'upload' && (
                <div className="space-y-1">
                  <input
                    type="file"
                    accept=".mp4,.webm"
                    onChange={(e) => setVideoFile(e.target.files?.[0] ?? null)}
                    className="w-full text-sm border rounded-lg p-2 bg-background"
                  />
                  <p className="text-xs text-muted-foreground">Solo MP4 o WebM — son los formatos que reproduce el visor</p>
                </div>
              )}
              {videoMode === 'file' && sourceMode === 'repository' && (
                <RepoFilePickerField repoFile={repoFile}
                  onPick={() => setShowRepoPicker(true)}
                  onClear={() => setRepoFile(null)} />
              )}
            </div>
          )}
          {showRepoPicker && (form.type === 'PDF' || form.type === 'VIDEO') && (
            <AssignRepositoryModal
              selectionMode
              fileTypeFilter={form.type === 'PDF' ? 'PDF' : 'VIDEO'}
              onSelect={(f) => { setRepoFile(f); setShowRepoPicker(false) }}
              onClose={() => setShowRepoPicker(false)}
            />
          )}
          {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>Cancelar</Button>
            <Button type="submit" size="sm" disabled={saving}>{saving ? 'Creando…' : 'Crear lección'}</Button></div>
        </form></div></div>
  )
}

function CreateEvaluationModal({ moduleId, lessons, onClose, onCreated }: {
  moduleId: string; lessons: TrainingLesson[]; onClose: () => void; onCreated: () => void
}) {
  const [form, setForm] = useState({ title: '', type: 'QUIZ', description: '', max_score: '100', passing_score: '60', max_attempts: '3' })
  const [afterLessonId, setAfterLessonId] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="font-semibold">Nueva evaluación</h3>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X size={16} /></button></div>
        <form onSubmit={async (e) => {
          e.preventDefault(); setError(null); setSaving(true)
          try {
            const created = await trainingService.createEvaluation(moduleId, {
              title: form.title.trim(),
              type: form.type,
              description: form.description.trim() || undefined,
              max_score: parseInt(form.max_score, 10),
              passing_score: parseInt(form.passing_score, 10),
              max_attempts: parseInt(form.max_attempts, 10),
            })
            if (afterLessonId) {
              await api.patch(`/training/evaluations/${created.public_id}`, {
                after_lesson_public_id: afterLessonId,
              })
            }
            onCreated()
          } catch (err: any) { setError(err?.detail ?? 'Error') } finally { setSaving(false) }
        }} className="space-y-3 px-5 py-4">
          <div className="space-y-1"><label className="text-xs font-medium">Título *</label>
            <Input required placeholder="Título" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
          <div className="space-y-1"><label className="text-xs font-medium">Tipo *</label>
            <select className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              <option value="QUIZ">Quiz</option><option value="PRACTICAL">Práctica</option></select></div>
          <div className="space-y-1"><label className="text-xs font-medium">Descripción</label>
            <textarea className="flex min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1"><label className="text-xs font-medium">Puntaje máximo</label>
              <Input type="number" min={1} value={form.max_score} onChange={(e) => setForm({ ...form, max_score: e.target.value })} /></div>
            <div className="space-y-1"><label className="text-xs font-medium">Puntaje aprobatorio</label>
              <Input type="number" min={0} value={form.passing_score} onChange={(e) => setForm({ ...form, passing_score: e.target.value })} /></div></div>
          <div className="space-y-1">
            <label className="text-xs font-medium">Intentos máximos</label>
            <Input type="number" min={1} value={form.max_attempts} onChange={(e) => setForm({ ...form, max_attempts: e.target.value })} />
            <p className="text-[10px] text-muted-foreground">Cantidad de veces que el docente puede intentar. Tras agotarlos, podrá avanzar sin aprobar.</p>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium">Mostrar después de lección</label>
            <select
              value={afterLessonId}
              onChange={(e) => setAfterLessonId(e.target.value)}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            >
              <option value="">Al final del módulo (por defecto)</option>
              {lessons.map((lesson) => (
                <option key={lesson.public_id} value={lesson.public_id}>
                  {lesson.title}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              La evaluación aparecerá cuando el docente complete esta lección
            </p>
          </div>
          {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>Cancelar</Button>
            <Button type="submit" size="sm" disabled={saving}>{saving ? 'Creando…' : 'Crear evaluación'}</Button></div>
        </form></div></div>
  )
}

function CreateQuestionModal({ evaluationId, onClose, onCreated }: {
  evaluationId: string; onClose: () => void; onCreated: () => void
}) {
  const [question, setQuestion] = useState('')
  const [options, setOptions] = useState(['', '', '', ''])
  const [correctOption, setCorrectOption] = useState(0)
  const [points, setPoints] = useState('10')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg rounded-lg border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="font-semibold">Nueva pregunta</h3>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X size={16} /></button></div>
        <form onSubmit={async (e) => {
          e.preventDefault(); setError(null); setSaving(true)
          try { await trainingService.createQuestion(evaluationId, { question: question.trim(), options: options.map((text, i) => ({ id: i, text: text.trim() })), correct_option: correctOption, points: parseInt(points, 10) }); onCreated()
          } catch (err: any) { setError(err?.detail ?? 'Error') } finally { setSaving(false) }
        }} className="space-y-3 px-5 py-4">
          <div className="space-y-1"><label className="text-xs font-medium">Pregunta *</label>
            <textarea required className="flex min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={question} onChange={(e) => setQuestion(e.target.value)} /></div>
          <div className="space-y-2"><label className="text-xs font-medium">Opciones (selecciona la correcta)</label>
            {options.map((opt, i) => (<div key={i} className="flex items-center gap-2">
              <input type="radio" name="correct" checked={correctOption === i} onChange={() => setCorrectOption(i)} className="accent-primary" />
              <Input required placeholder={`Opción ${String.fromCharCode(65 + i)}`} value={opt} onChange={(e) => { const c = [...options]; c[i] = e.target.value; setOptions(c) }} /></div>))}</div>
          <div className="space-y-1"><label className="text-xs font-medium">Puntos</label>
            <Input type="number" min={1} value={points} onChange={(e) => setPoints(e.target.value)} className="w-24" /></div>
          {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>Cancelar</Button>
            <Button type="submit" size="sm" disabled={saving}>{saving ? 'Creando…' : 'Crear pregunta'}</Button></div>
        </form></div></div>
  )
}

function EnrollTeacherModal({ programId, enrolledIds, onClose, onEnrolled }: {
  programId: string; enrolledIds: string[]; onClose: () => void; onEnrolled: () => void
}) {
  const [schools, setSchools] = useState<School[]>([])
  const [selectedSchool, setSelectedSchool] = useState('')
  const [teachers, setTeachers] = useState<User[]>([])
  const [selectedTeachers, setSelectedTeachers] = useState<string[]>([])
  const [enrolling, setEnrolling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    academicService.listSchools().then(setSchools).catch(() => setSchools([]))
  }, [])

  useEffect(() => {
    if (!selectedSchool) {
      setTeachers([])
      return
    }
    academicService.listSchoolTeachers(selectedSchool).then(setTeachers).catch(() => setTeachers([]))
  }, [selectedSchool])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="font-semibold">Inscribir docente</h3>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X size={16} /></button>
        </div>
        <div className="space-y-3 px-5 py-4">
          <div className="space-y-1">
            <label className="text-sm font-medium">Colegio</label>
            <select
              value={selectedSchool}
              onChange={(e) => {
                setSelectedSchool(e.target.value)
                setSelectedTeachers([])
              }}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            >
              <option value="">Seleccionar colegio...</option>
              {schools.map((s) => (
                <option key={s.public_id} value={s.public_id}>{s.name}</option>
              ))}
            </select>
          </div>

          {selectedSchool && (
            <div className="space-y-1">
              <label className="text-sm font-medium">
                Docentes del colegio
                {selectedTeachers.length > 0 && (
                  <span className="ml-2 text-xs text-primary font-normal">
                    {selectedTeachers.length} seleccionado(s)
                  </span>
                )}
              </label>
              {teachers.length === 0 ? (
                <p className="text-sm text-muted-foreground py-3 text-center border rounded-lg">
                  No hay docentes en este colegio
                </p>
              ) : (
                <div className="border rounded-lg divide-y max-h-48 overflow-y-auto">
                  {teachers.map((teacher) => {
                    const isSelected = selectedTeachers.includes(teacher.public_id)
                    const isAlreadyEnrolled = enrolledIds.includes(teacher.public_id)
                    return (
                      <label
                        key={teacher.public_id}
                        className={`flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-muted/50 transition-colors ${isAlreadyEnrolled ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          disabled={isAlreadyEnrolled}
                          onChange={() => {
                            if (isAlreadyEnrolled) return
                            setSelectedTeachers((prev) =>
                              isSelected
                                ? prev.filter((id) => id !== teacher.public_id)
                                : [...prev, teacher.public_id],
                            )
                          }}
                          className="rounded"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">
                            {teacher.first_name} {teacher.last_name}
                          </p>
                          <p className="text-xs text-muted-foreground truncate">
                            {teacher.email}
                          </p>
                        </div>
                        {isAlreadyEnrolled && (
                          <span className="text-xs text-green-600 shrink-0">
                            Ya inscrito
                          </span>
                        )}
                      </label>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

          <button
            onClick={async () => {
              if (selectedTeachers.length === 0) return
              setEnrolling(true)
              setError(null)
              try {
                for (const userId of selectedTeachers) {
                  await trainingService.enrollTeacher(programId, userId)
                }
                onEnrolled()
              } catch (err: any) {
                setError(err?.detail ?? 'Error al inscribir')
              } finally {
                setEnrolling(false)
              }
            }}
            disabled={selectedTeachers.length === 0 || enrolling}
            className="w-full py-2 rounded-lg bg-primary text-primary-foreground font-medium disabled:opacity-50"
          >
            {enrolling
              ? 'Inscribiendo...'
              : `Inscribir${selectedTeachers.length > 0 ? ` (${selectedTeachers.length})` : ''}`}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Templates Tab ───────────────────────────────────────────────────────────

interface Template {
  public_id: string
  title: string
  description: string | null
  file_name: string
  file_size: number | null
  uploaded_by: number | null
  created_at: string
  updated_at: string
}

function TemplatesTab({ program }: { program: TrainingProgram }) {
  const { isAdmin, hasRole } = useAuthStore()
  const [templates, setTemplates] = useState<Template[]>([])
  const [loadingTemplates, setLoadingTemplates] = useState(false)
  const [uploadingDoc, setUploadingDoc] = useState(false)

  const canManage = isAdmin() || hasRole('TRAINER') || hasRole('SUPER_TRAINER')

  useEffect(() => {
    setLoadingTemplates(true)
    api
      .get<Template[]>(`/training/programs/${program.public_id}/templates`)
      .then(setTemplates)
      .finally(() => setLoadingTemplates(false))
  }, [program.public_id])

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold">Plantillas del programa</h3>
            <p className="text-sm text-muted-foreground">
              Documentos que los docentes pueden descargar para sus entregas
            </p>
          </div>

          {canManage && (
            <label
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium cursor-pointer bg-primary text-white hover:bg-primary/90 transition-colors ${
                uploadingDoc ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              <Upload size={16} />
              {uploadingDoc ? 'Subiendo...' : 'Subir plantilla'}
              <input
                type="file"
                accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx"
                className="hidden"
                disabled={uploadingDoc}
                onChange={async (e) => {
                  const file = e.target.files?.[0]
                  if (!file) return
                  const title = file.name.replace(/\.[^/.]+$/, '')
                  setUploadingDoc(true)
                  try {
                    const formData = new FormData()
                    formData.append('file', file)
                    formData.append('title', title)
                    await api.postForm(
                      `/training/programs/${program.public_id}/templates`,
                      formData,
                    )
                    const updated = await api.get<Template[]>(
                      `/training/programs/${program.public_id}/templates`,
                    )
                    setTemplates(updated)
                    toast({ title: 'Plantilla subida', variant: 'success' })
                  } catch {
                    toast({ title: 'Error al subir', variant: 'destructive' })
                  } finally {
                    setUploadingDoc(false)
                    e.target.value = ''
                  }
                }}
              />
            </label>
          )}
        </div>

        {loadingTemplates ? (
          <div className="flex justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
          </div>
        ) : templates.length === 0 ? (
          <div className="border-2 border-dashed rounded-xl p-10 text-center">
            <FileText size={32} className="mx-auto text-muted-foreground mb-3" />
            <p className="text-sm font-medium">Sin plantillas</p>
            <p className="text-xs text-muted-foreground mt-1">
              {canManage
                ? 'Sube documentos Word, PDF o Excel para que los docentes los usen en sus entregas'
                : 'El trainer aún no ha subido plantillas para este programa'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {templates.map((template) => (
              <div
                key={template.public_id}
                className="flex items-center gap-4 p-4 rounded-xl border bg-card hover:bg-muted/30 transition-colors"
              >
                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${getFileColor(
                    template.file_name,
                  )}`}
                >
                  <FileText size={20} className="text-white" />
                </div>

                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">{template.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {template.file_name}
                    {template.file_size && (
                      <span className="ml-2">· {formatFileSize(template.file_size)}</span>
                    )}
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={async () => {
                      const { url, file_name } = await api.get<{
                        url: string
                        file_name: string
                      }>(
                        `/training/programs/templates/${template.public_id}/download`,
                      )
                      const a = document.createElement('a')
                      a.href = url
                      a.download = file_name
                      a.click()
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                  >
                    <Download size={14} />
                    Descargar
                  </button>

                  {canManage && (
                    <button
                      onClick={async () => {
                        if (!confirm('¿Eliminar esta plantilla?')) return
                        await api.delete(
                          `/training/programs/templates/${template.public_id}`,
                        )
                        setTemplates((prev) =>
                          prev.filter((t) => t.public_id !== template.public_id),
                        )
                        toast({ title: 'Plantilla eliminada', variant: 'default' })
                      }}
                      className="p-1.5 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function getFileColor(fileName: string) {
  const ext = fileName.split('.').pop()?.toLowerCase()
  if (['doc', 'docx'].includes(ext ?? '')) return 'bg-blue-500'
  if (['xls', 'xlsx'].includes(ext ?? '')) return 'bg-green-600'
  if (['ppt', 'pptx'].includes(ext ?? '')) return 'bg-orange-500'
  if (ext === 'pdf') return 'bg-red-500'
  return 'bg-gray-500'
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function RepoFilePickerField({
  repoFile,
  onPick,
  onClear,
}: {
  repoFile: RepoFile | null
  onPick: () => void
  onClear: () => void
}) {
  if (repoFile) {
    return (
      <div className="flex items-center gap-3 rounded-lg border bg-muted/30 p-3">
        <FileText size={16} className="shrink-0 text-primary" />
        <span className="flex-1 truncate text-sm">{repoFile.name}</span>
        <button
          type="button"
          onClick={onClear}
          className="text-xs text-muted-foreground hover:text-destructive"
        >
          Cambiar
        </button>
      </div>
    )
  }
  return (
    <button
      type="button"
      onClick={onPick}
      className="w-full rounded-lg border-2 border-dashed py-3 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-primary"
    >
      Seleccionar del repositorio...
    </button>
  )
}

// ── Resources Tab ───────────────────────────────────────────────────────────

interface ResourcesData {
  folders: { public_id: string; name: string; description: string | null; file_count: number }[]
  files: { public_id: string; name: string; file_name: string; file_size: number | null; file_type: string | null }[]
}

export function ResourcesTab({
  program,
  canManage,
}: {
  program: TrainingProgram
  canManage: boolean
}) {
  const [data, setData] = useState<ResourcesData>({ folders: [], files: [] })
  const [loading, setLoading] = useState(true)
  const [showAssign, setShowAssign] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const res = await api.get<ResourcesData>(
        `/repository/programs/${program.public_id}/resources`,
      )
      setData(res)
    } catch (err: any) {
      toast({ title: err?.detail ?? 'Error al cargar recursos', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [program.public_id])

  async function unassignFolder(folderId: string) {
    try {
      await api.delete(`/repository/programs/${program.public_id}/folders/${folderId}`)
      toast({ title: 'Carpeta desasignada', variant: 'success' })
      load()
    } catch (err: any) {
      toast({ title: err?.detail ?? 'Error', variant: 'destructive' })
    }
  }

  async function unassignFile(fileId: string) {
    try {
      await api.delete(`/repository/programs/${program.public_id}/files/${fileId}`)
      toast({ title: 'Archivo desasignado', variant: 'success' })
      load()
    } catch (err: any) {
      toast({ title: err?.detail ?? 'Error', variant: 'destructive' })
    }
  }

  async function downloadFile(fileId: string) {
    try {
      const res = await api.get<{ url: string; file_name: string }>(
        `/repository/files/${fileId}/download`,
      )
      window.open(res.url, '_blank')
    } catch (err: any) {
      toast({ title: err?.detail ?? 'Error', variant: 'destructive' })
    }
  }

  if (loading) {
    return <div className="p-6 text-sm text-muted-foreground">Cargando…</div>
  }

  const empty = data.folders.length === 0 && data.files.length === 0

  return (
    <div className="p-6 space-y-6">
      {canManage && (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setShowAssign(true)}>
            <Plus size={14} className="mr-1" /> Asignar del repositorio
          </Button>
        </div>
      )}

      {empty && (
        <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          No hay recursos asignados a este programa.
        </p>
      )}

      {data.folders.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold">Carpetas</h4>
          {data.folders.map((folder) => (
            <div
              key={folder.public_id}
              className="group flex items-center gap-3 rounded-lg border p-3 hover:bg-muted/30"
            >
              <Folder size={18} className="shrink-0 text-yellow-500" />
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-medium">{folder.name}</p>
                <p className="text-xs text-muted-foreground">
                  {folder.file_count} archivo{folder.file_count === 1 ? '' : 's'}
                </p>
              </div>
              {canManage && (
                <button
                  type="button"
                  onClick={() => unassignFolder(folder.public_id)}
                  className="shrink-0 rounded-md p-1 text-muted-foreground opacity-0 hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                  aria-label="Desasignar carpeta"
                >
                  <X size={16} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {data.files.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold">Archivos individuales</h4>
          {data.files.map((file) => (
            <div
              key={file.public_id}
              className="group flex items-center gap-3 rounded-lg border p-3 hover:bg-muted/30"
            >
              <div
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded ${getFileColor(file.file_name)}`}
              >
                <FileText size={12} className="text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-medium">{file.name}</p>
                <p className="truncate text-xs text-muted-foreground">{file.file_name}</p>
              </div>
              <button
                type="button"
                onClick={() => downloadFile(file.public_id)}
                className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="Descargar"
              >
                <Download size={16} />
              </button>
              {canManage && (
                <button
                  type="button"
                  onClick={() => unassignFile(file.public_id)}
                  className="shrink-0 rounded-md p-1 text-muted-foreground opacity-0 hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                  aria-label="Desasignar archivo"
                >
                  <X size={16} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {showAssign && (
        <AssignRepositoryModal
          programId={program.public_id}
          onClose={() => setShowAssign(false)}
          onAssigned={() => load()}
        />
      )}
    </div>
  )
}

// ── Assign Repository Modal ─────────────────────────────────────────────────

interface RepoFolder {
  public_id: string
  name: string
  description?: string | null
  file_count?: number
}

interface RepoFile {
  public_id: string
  name: string
  file_name: string
  file_size?: number | null
  file_type?: string | null
}

interface AssignRepositoryModalProps {
  programId?: string
  onClose: () => void
  onAssigned?: () => void
  selectionMode?: boolean
  fileTypeFilter?: 'PDF' | 'VIDEO'
  onSelect?: (file: RepoFile) => void
}

// Espejo de LESSON_FILE_EXTENSIONS['VIDEO'] en el backend: son los formatos que
// el visor reproduce. Ofrecer .mov/.avi aquí sería un callejón sin salida — el
// picker los listaría y el servidor los rechazaría con 400 al guardar.
const VIDEO_EXTS = ['mp4', 'webm']

export function AssignRepositoryModal({
  programId,
  onClose,
  onAssigned,
  selectionMode = false,
  fileTypeFilter,
  onSelect,
}: AssignRepositoryModalProps) {
  const [contents, setContents] = useState<{ subfolders: RepoFolder[]; files: RepoFile[] }>({
    subfolders: [],
    files: [],
  })
  const [breadcrumb, setBreadcrumb] = useState<RepoFolder[]>([])
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)

  async function loadRoot() {
    setLoading(true)
    try {
      const data = await api.get<RepoFolder[]>('/repository/folders')
      setContents({ subfolders: data, files: [] })
      setBreadcrumb([])
    } catch (err: any) {
      toast({ title: err?.detail ?? 'Error al cargar', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }

  async function openFolder(folder: RepoFolder) {
    setLoading(true)
    try {
      const data = await api.get<{
        subfolders: RepoFolder[]
        files: RepoFile[]
        breadcrumb: RepoFolder[]
      }>(`/repository/folders/${folder.public_id}`)
      setContents({ subfolders: data.subfolders, files: data.files })
      setBreadcrumb(data.breadcrumb)
    } catch (err: any) {
      toast({ title: err?.detail ?? 'Error', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRoot()
  }, [])

  async function assignFolder(folder: RepoFolder) {
    if (!programId) return
    setBusy(true)
    try {
      await api.post(`/repository/programs/${programId}/assign-folder`, {
        folder_id: folder.public_id,
      })
      toast({ title: `Carpeta "${folder.name}" asignada`, variant: 'success' })
      onAssigned?.()
    } catch (err: any) {
      toast({ title: err?.detail ?? 'Error al asignar', variant: 'destructive' })
    } finally {
      setBusy(false)
    }
  }

  async function assignFile(file: RepoFile) {
    if (!programId) return
    setBusy(true)
    try {
      await api.post(`/repository/programs/${programId}/assign-file`, {
        file_id: file.public_id,
      })
      toast({ title: `Archivo "${file.name}" asignado`, variant: 'success' })
      onAssigned?.()
    } catch (err: any) {
      toast({ title: err?.detail ?? 'Error al asignar', variant: 'destructive' })
    } finally {
      setBusy(false)
    }
  }

  function fileMatchesFilter(file: RepoFile): boolean {
    if (!fileTypeFilter) return true
    const ext = (file.file_type ?? file.file_name.split('.').pop() ?? '').toLowerCase()
    if (fileTypeFilter === 'PDF') return ext === 'pdf'
    return VIDEO_EXTS.includes(ext)
  }

  const visibleFiles = contents.files.filter(fileMatchesFilter)

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/80 p-4">
      <div className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-xl bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b p-6">
          <h2 className="font-semibold">
            {selectionMode ? 'Seleccionar del repositorio' : 'Asignar del repositorio'}
          </h2>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-muted">
            <X size={20} />
          </button>
        </div>

        <div className="flex items-center gap-1 border-b px-6 py-3 text-sm">
          <button
            type="button"
            onClick={loadRoot}
            className="text-muted-foreground hover:text-foreground"
          >
            Repositorio
          </button>
          {breadcrumb.map((crumb, i) => (
            <span key={crumb.public_id} className="flex items-center gap-1">
              <ChevronRight size={14} className="text-muted-foreground" />
              <button
                type="button"
                onClick={() => openFolder(crumb)}
                className={
                  i === breadcrumb.length - 1
                    ? 'font-medium'
                    : 'text-muted-foreground hover:text-foreground'
                }
              >
                {crumb.name}
              </button>
            </span>
          ))}
        </div>

        <div className="flex-1 space-y-2 overflow-y-auto p-6">
          {loading && (
            <p className="py-8 text-center text-sm text-muted-foreground">Cargando…</p>
          )}

          {!loading &&
            contents.subfolders.map((folder) => (
              <div
                key={folder.public_id}
                className="flex items-center gap-3 rounded-lg border p-3 hover:bg-muted/30"
              >
                <Folder size={18} className="shrink-0 text-yellow-500" />
                <button
                  type="button"
                  onClick={() => openFolder(folder)}
                  className="flex-1 truncate text-left text-sm font-medium"
                >
                  {folder.name}
                </button>
                {!selectionMode && (
                  <button
                    type="button"
                    onClick={() => assignFolder(folder)}
                    disabled={busy}
                    className="flex shrink-0 items-center gap-1 rounded-lg bg-primary px-3 py-1 text-xs text-white hover:bg-primary/90 disabled:opacity-50"
                  >
                    <Plus size={12} /> Asignar carpeta
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => openFolder(folder)}
                  className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-muted"
                  aria-label="Abrir"
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            ))}

          {!loading &&
            visibleFiles.map((file) => (
              <div
                key={file.public_id}
                className="flex items-center gap-3 rounded-lg border p-3 hover:bg-muted/30"
              >
                <div
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded ${getFileColor(file.file_name)}`}
                >
                  <FileText size={12} className="text-white" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{file.name}</p>
                  <p className="truncate text-xs text-muted-foreground">{file.file_name}</p>
                </div>
                <button
                  type="button"
                  onClick={() => (selectionMode ? onSelect?.(file) : assignFile(file))}
                  disabled={busy}
                  className="flex shrink-0 items-center gap-1 rounded-lg bg-primary px-3 py-1 text-xs text-white hover:bg-primary/90 disabled:opacity-50"
                >
                  <Plus size={12} /> {selectionMode ? 'Seleccionar' : 'Asignar'}
                </button>
              </div>
            ))}

          {!loading &&
            contents.subfolders.length === 0 &&
            visibleFiles.length === 0 && (
              <p className="py-8 text-center text-sm text-muted-foreground">
                {fileTypeFilter
                  ? `No hay archivos compatibles con ${fileTypeFilter} en esta carpeta.`
                  : 'Carpeta vacía'}
              </p>
            )}
        </div>

        <div className="border-t p-4">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-lg border py-2 text-sm hover:bg-muted"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  )
}
