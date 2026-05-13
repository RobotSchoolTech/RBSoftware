'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  ArrowLeft,
  ArrowRight,
  Award,
  BookOpen,
  Check,
  CheckCircle2,
  Circle,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Download,
  FileText,
  Folder,
  Lock,
  Menu,
  Send,
  Video,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import type { TrainingProgram } from '@/lib/types'
import type {
  TrainingModule,
  TrainingLesson,
  TrainingEvaluation,
  QuizQuestion,
  TrainingSubmission,
} from '@/services/training'
import * as trainingService from '@/services/training'
import { RubricEditor } from '@/components/rubric-editor'

// ── Types ───────────────────────────────────────────────────────────────────

interface FlatLesson extends TrainingLesson {
  moduleTitle: string
  moduleIndex: number
  flatIndex: number
}

interface ModuleEvals {
  moduleId: string
  evaluations: TrainingEvaluation[]
}

interface Template {
  public_id: string
  title: string
  file_name: string
}

interface Props {
  program: TrainingProgram
  modules: TrainingModule[]
  reload: () => void
}

// ── Main component ──────────────────────────────────────────────────────────

export function TeacherProgramView({ program, modules }: Props) {
  const router = useRouter()
  const publishedModules = modules.filter((m) => m.is_published)

  const [allLessons, setAllLessons] = useState<FlatLesson[]>([])
  const [moduleEvals, setModuleEvals] = useState<ModuleEvals[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [completedSet, setCompletedSet] = useState<Set<string>>(new Set())
  const [submissionMap, setSubmissionMap] = useState<Map<string, TrainingSubmission>>(new Map())
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [loading, setLoading] = useState(true)
  const [templates, setTemplates] = useState<Template[]>([])

  // Load all content on mount
  useEffect(() => {
    async function loadAll() {
      setLoading(true)
      const flat: FlatLesson[] = []
      const evals: ModuleEvals[] = []
      const subs = new Map<string, TrainingSubmission>()
      let idx = 0

      for (let mi = 0; mi < publishedModules.length; mi++) {
        const mod = publishedModules[mi]
        const [lessons, evaluations] = await Promise.all([
          trainingService.listLessons(mod.public_id),
          trainingService.listEvaluations(mod.public_id),
        ])
        const published = lessons.filter((l) => l.is_published)
        for (const l of published) {
          flat.push({ ...l, moduleTitle: mod.title, moduleIndex: mi, flatIndex: idx })
          idx++
        }
        const pubEvals = evaluations.filter((e) => e.is_published)
        if (pubEvals.length > 0) {
          evals.push({ moduleId: mod.public_id, evaluations: pubEvals })
          // Load submissions for each evaluation
          await Promise.all(
            pubEvals.map(async (ev) => {
              try {
                const sub = await trainingService.getMySubmission(ev.public_id)
                subs.set(ev.public_id, sub)
              } catch {}
            })
          )
        }
      }

      // Load completed lesson IDs from backend
      let completedIds: string[] = []
      try {
        completedIds = await trainingService.getMyCompletedLessons(program.public_id)
      } catch {}

      setAllLessons(flat)
      setModuleEvals(evals)
      setSubmissionMap(subs)
      setCompletedSet(new Set(completedIds))
      setLoading(false)
    }
    if (publishedModules.length > 0) loadAll()
    else setLoading(false)
  }, [])

  useEffect(() => {
    api
      .get<Template[]>(`/training/programs/${program.public_id}/templates`)
      .then(setTemplates)
      .catch(() => {})
  }, [program.public_id])

  const currentLesson = allLessons[currentIndex] ?? null
  const totalLessons = allLessons.length
  const completedCount = completedSet.size
  const progressPct = totalLessons > 0 ? Math.round((completedCount / totalLessons) * 100) : 0
  const isCurrentCompleted = currentLesson ? completedSet.has(currentLesson.public_id) : false

  // Find evaluations for current module
  const currentModuleId = currentLesson
    ? publishedModules[currentLesson.moduleIndex]?.public_id
    : null
  const currentModuleEvalData = moduleEvals.find((me) => me.moduleId === currentModuleId)
  const isLastLessonOfModule = currentLesson
    ? !allLessons[currentIndex + 1] || allLessons[currentIndex + 1].moduleIndex !== currentLesson.moduleIndex
    : false

  const matchedEvals =
    currentModuleEvalData?.evaluations.filter((ev) => {
      if (ev.after_lesson_public_id) {
        return currentLesson?.public_id === ev.after_lesson_public_id
      }
      return isLastLessonOfModule
    }) ?? []

  function isModuleUnlocked(moduleIndex: number): boolean {
    if (moduleIndex === 0) return true
    const prevModuleId = publishedModules[moduleIndex - 1]?.public_id
    if (!prevModuleId) return false

    // All lessons of previous module must be completed
    const prevLessons = allLessons.filter((l) => l.moduleIndex === moduleIndex - 1)
    const allLessonsCompleted = prevLessons.length > 0 && prevLessons.every((l) => completedSet.has(l.public_id))

    // All evaluations of previous module must be passed OR have attempts exhausted
    const prevEvalData = moduleEvals.find((me) => me.moduleId === prevModuleId)
    const allEvalsCleared = !prevEvalData || prevEvalData.evaluations.every((ev) => {
      const sub = submissionMap.get(ev.public_id)
      if (sub?.status !== 'GRADED') return false
      const threshold = Math.round(ev.passing_score * ev.max_score / 100)
      const passed = (sub.score ?? 0) >= threshold
      const exhausted = sub.attempts_used >= ev.max_attempts
      return passed || exhausted
    })

    return allLessonsCompleted && allEvalsCleared
  }

  function canGoNext(): boolean {
    if (currentIndex >= totalLessons - 1) return false
    const nextLesson = allLessons[currentIndex + 1]
    return isModuleUnlocked(nextLesson.moduleIndex)
  }

  function goNext() {
    if (currentIndex < totalLessons - 1) {
      setCurrentIndex((i) => i + 1)
      window.scrollTo(0, 0)
    }
  }

  function goPrev() {
    if (currentIndex > 0) {
      setCurrentIndex((i) => i - 1)
      window.scrollTo(0, 0)
    }
  }

  async function markComplete() {
    if (!currentLesson || isCurrentCompleted) return
    try {
      await trainingService.completeLesson(currentLesson.public_id)
      setCompletedSet((prev) => new Set([...prev, currentLesson.public_id]))
      goNext()
    } catch {}
  }

  if (loading) {
    return <div className="flex items-center justify-center py-20 text-muted-foreground">Cargando programa…</div>
  }

  if (totalLessons === 0) {
    return (
      <div className="space-y-4">
        <button onClick={() => router.push('/training/my-programs')} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft size={14} /> Mis Programas
        </button>
        <p className="py-12 text-center text-muted-foreground">No hay contenido publicado en este programa</p>
      </div>
    )
  }

  // Group lessons by module for sidebar
  const moduleGroups: { title: string; lessons: FlatLesson[] }[] = []
  for (const l of allLessons) {
    if (!moduleGroups[l.moduleIndex]) {
      moduleGroups[l.moduleIndex] = { title: l.moduleTitle, lessons: [] }
    }
    moduleGroups[l.moduleIndex].lessons.push(l)
  }

  return (
    <div className="flex h-full flex-col">
      {/* ── Sticky header ── */}
      <div className="sticky top-0 z-10 shrink-0 border-b bg-background/95 backdrop-blur px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="rounded-md p-1 hover:bg-muted md:hidden"
            >
              <Menu size={18} />
            </button>
            <button
              onClick={() => router.push('/training/my-programs')}
              className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft size={14} /> Mis Programas
            </button>
          </div>
          <span className="text-sm font-medium truncate max-w-[200px] sm:max-w-none">{program.name}</span>
        </div>
        <div className="mt-2">
          <div className="flex justify-between text-xs text-muted-foreground mb-1">
            <span>{completedCount} de {totalLessons} lecciones</span>
            <span>{progressPct}%</span>
          </div>
          <div className="h-1.5 bg-muted rounded-full overflow-hidden">
            <div className="h-full bg-primary rounded-full transition-all duration-300" style={{ width: `${progressPct}%` }} />
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* ── Sidebar ── */}
        <div className={`${sidebarOpen ? 'block' : 'hidden'} md:block w-72 shrink-0 border-r bg-muted/20 overflow-y-auto`}>
          <div className="p-3">
            {moduleGroups.map((group, gi) => {
              const unlocked = isModuleUnlocked(gi)
              return (
                <div key={gi} className="mb-4">
                  <div
                    title={!unlocked ? 'Completa el módulo anterior para desbloquear' : undefined}
                    className={`flex items-center gap-1.5 px-2 py-1 text-[10px] font-bold uppercase tracking-widest ${
                      unlocked ? 'text-muted-foreground' : 'text-muted-foreground/40'
                    }`}
                  >
                    {!unlocked && <Lock size={10} />}
                    <span>Módulo {gi + 1}</span>
                  </div>
                  <p className={`px-2 mb-2 text-xs font-medium truncate ${
                    unlocked ? 'text-muted-foreground' : 'text-muted-foreground/40'
                  }`}>{group.title}</p>
                  {group.lessons.map((l) => {
                    const isActive = l.flatIndex === currentIndex
                    const isDone = completedSet.has(l.public_id)
                    return (
                      <button
                        key={l.public_id}
                        onClick={() => { if (!unlocked) return; setCurrentIndex(l.flatIndex); setSidebarOpen(false) }}
                        className={`w-full flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors mb-0.5 ${
                          isActive
                            ? 'bg-primary text-primary-foreground font-medium'
                            : unlocked
                              ? 'hover:bg-muted'
                              : 'opacity-40 cursor-not-allowed'
                        }`}
                      >
                        {isDone ? (
                          <CheckCircle2 size={14} className={isActive ? 'text-primary-foreground' : 'text-green-500'} />
                        ) : (
                          <Circle size={14} className={isActive ? 'text-primary-foreground/60' : 'text-muted-foreground/40'} />
                        )}
                        <span className="truncate">{l.title}</span>
                      </button>
                    )
                  })}
                </div>
              )
            })}
          </div>

          {/* Certificate card in sidebar */}
          <CertificateStatus programId={program.public_id} />

          <TemplatesSidebar templates={templates} />

          <ResourcesSidebar programId={program.public_id} />
        </div>

        {/* ── Main content ── */}
        <div className="flex-1 overflow-y-auto">
          {currentLesson && (
            <div className="max-w-3xl mx-auto px-6 py-8">
              {/* Lesson header */}
              <div className="mb-6">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                  <span>{currentLesson.moduleTitle}</span>
                  <span>·</span>
                  {currentLesson.type === 'PDF' && <FileText size={14} className="text-red-500" />}
                  {currentLesson.type === 'VIDEO' && <Video size={14} className="text-blue-500" />}
                  {currentLesson.type === 'TEXT' && <BookOpen size={14} />}
                  <span>{currentLesson.type}</span>
                  {currentLesson.duration_minutes && (
                    <>
                      <span>·</span>
                      <span>{currentLesson.duration_minutes} min</span>
                    </>
                  )}
                </div>
                <h1 className="text-2xl font-bold">{currentLesson.title}</h1>
              </div>

              {/* Content by type */}
              {currentLesson.type === 'TEXT' && currentLesson.content && (
                <div className="prose prose-lg dark:prose-invert max-w-none">
                  <p className="whitespace-pre-wrap leading-relaxed">{currentLesson.content}</p>
                </div>
              )}

              {currentLesson.type === 'PDF' && currentLesson.file_key && (
                <LessonPdfViewer lessonId={currentLesson.public_id} />
              )}

              {currentLesson.type === 'VIDEO' && (
                <LessonVideoPlayer lesson={currentLesson} />
              )}

              {/* Evaluations that match current lesson (linked) or end-of-module (unlinked) */}
              {matchedEvals.length > 0 && (
                <div className="mt-10 rounded-xl border-2 border-primary/20 bg-primary/5 p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                      <ClipboardList size={20} className="text-primary" />
                    </div>
                    <div>
                      <h3 className="font-semibold">Evaluación del módulo</h3>
                      <p className="text-sm text-muted-foreground">Completa la evaluación para avanzar</p>
                    </div>
                  </div>
                  {matchedEvals.map((ev) => (
                    <EvaluationCard key={ev.public_id} evaluation={ev} onSubmissionUpdate={(sub) => {
                      setSubmissionMap((prev) => new Map(prev).set(ev.public_id, sub))
                    }} />
                  ))}
                </div>
              )}

              {/* Bottom navigation */}
              <div className="flex items-center justify-between mt-12 pt-6 border-t">
                <button
                  onClick={goPrev}
                  disabled={currentIndex === 0}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg border hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <ArrowLeft size={16} /> Anterior
                </button>

                <button
                  onClick={markComplete}
                  disabled={isCurrentCompleted}
                  className={`flex items-center gap-2 px-6 py-2 rounded-lg font-medium transition-colors ${
                    isCurrentCompleted
                      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                      : 'bg-primary text-primary-foreground hover:bg-primary/90'
                  }`}
                >
                  {isCurrentCompleted ? (
                    <><CheckCircle2 size={16} /> Completada</>
                  ) : (
                    <><Check size={16} /> Marcar completada</>
                  )}
                </button>

                <button
                  onClick={goNext}
                  disabled={!canGoNext()}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg border hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Siguiente <ArrowRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function TemplatesSidebar({ templates }: { templates: Template[] }) {
  if (templates.length === 0) return null
  return (
    <div className="mx-3 mb-3 rounded-lg border bg-card">
      <div className="px-3 py-2 border-b">
        <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
          <FileText size={11} /> Plantillas
        </p>
      </div>
      <div className="p-2 space-y-1">
        {templates.map((template) => (
          <button
            key={template.public_id}
            onClick={async () => {
              const { url, file_name } = await api.get<{ url: string; file_name: string }>(
                `/training/programs/templates/${template.public_id}/download`,
              )
              const a = document.createElement('a')
              a.href = url
              a.download = file_name
              a.click()
            }}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted/50 transition-colors text-left"
            title={template.file_name}
          >
            <div
              className={`w-6 h-6 rounded flex items-center justify-center shrink-0 ${getFileColor(
                template.file_name,
              )}`}
            >
              <FileText size={10} className="text-white" />
            </div>
            <span className="flex-1 min-w-0 text-xs truncate">{template.title}</span>
            <Download size={12} className="text-muted-foreground shrink-0" />
          </button>
        ))}
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

interface ResourceFile {
  public_id: string
  name: string
  file_name: string
}

interface ResourceFolder {
  public_id: string
  name: string
  file_count: number
}

function ResourcesSidebar({ programId }: { programId: string }) {
  const [folders, setFolders] = useState<ResourceFolder[]>([])
  const [files, setFiles] = useState<ResourceFile[]>([])
  const [expanded, setExpanded] = useState<Record<string, ResourceFile[] | undefined>>({})

  useEffect(() => {
    api
      .get<{ folders: ResourceFolder[]; files: ResourceFile[] }>(
        `/repository/programs/${programId}/resources`,
      )
      .then((data) => {
        setFolders(data.folders)
        setFiles(data.files)
      })
      .catch(() => {})
  }, [programId])

  async function toggleFolder(folder: ResourceFolder) {
    if (expanded[folder.public_id] !== undefined) {
      setExpanded((s) => ({ ...s, [folder.public_id]: undefined }))
      return
    }
    try {
      const data = await api.get<{ files: ResourceFile[] }>(
        `/repository/folders/${folder.public_id}`,
      )
      setExpanded((s) => ({ ...s, [folder.public_id]: data.files }))
    } catch {
      setExpanded((s) => ({ ...s, [folder.public_id]: [] }))
    }
  }

  async function downloadFile(fileId: string) {
    try {
      const { url } = await api.get<{ url: string; file_name: string }>(
        `/repository/files/${fileId}/download`,
      )
      window.open(url, '_blank')
    } catch {}
  }

  if (folders.length === 0 && files.length === 0) return null

  return (
    <div className="mx-3 mb-3 rounded-lg border bg-card">
      <div className="border-b px-3 py-2">
        <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
          <Folder size={11} /> Recursos
        </p>
      </div>
      <div className="space-y-1 p-2">
        {folders.map((folder) => {
          const open = expanded[folder.public_id] !== undefined
          return (
            <div key={folder.public_id}>
              <button
                onClick={() => toggleFolder(folder)}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left transition-colors hover:bg-muted/50"
              >
                {open ? (
                  <ChevronDown size={12} className="shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight size={12} className="shrink-0 text-muted-foreground" />
                )}
                <Folder size={12} className="shrink-0 text-yellow-500" />
                <span className="min-w-0 flex-1 truncate text-xs">{folder.name}</span>
                <span className="shrink-0 text-[10px] text-muted-foreground">
                  {folder.file_count}
                </span>
              </button>
              {open && expanded[folder.public_id] && (
                <div className="ml-5 mt-1 space-y-1">
                  {(expanded[folder.public_id] ?? []).map((f) => (
                    <button
                      key={f.public_id}
                      onClick={() => downloadFile(f.public_id)}
                      className="flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-muted/50"
                      title={f.file_name}
                    >
                      <div
                        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded ${getFileColor(f.file_name)}`}
                      >
                        <FileText size={8} className="text-white" />
                      </div>
                      <span className="min-w-0 flex-1 truncate text-xs">{f.name}</span>
                      <Download size={10} className="shrink-0 text-muted-foreground" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}
        {files.map((file) => (
          <button
            key={file.public_id}
            onClick={() => downloadFile(file.public_id)}
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left transition-colors hover:bg-muted/50"
            title={file.file_name}
          >
            <div
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded ${getFileColor(file.file_name)}`}
            >
              <FileText size={10} className="text-white" />
            </div>
            <span className="min-w-0 flex-1 truncate text-xs">{file.name}</span>
            <Download size={12} className="shrink-0 text-muted-foreground" />
          </button>
        ))}
      </div>
    </div>
  )
}

// ── PDF Viewer ──────────────────────────────────────────────────────────────

function LessonPdfViewer({ lessonId }: { lessonId: string }) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    trainingService.getLessonViewUrl(lessonId)
      .then((data) => setUrl(data.url))
      .catch(() => {})
  }, [lessonId])

  if (!url) return <div className="h-[70vh] rounded-lg border flex items-center justify-center text-muted-foreground">Cargando PDF…</div>

  return (
    <iframe src={url} className="h-[70vh] w-full rounded-lg border" />
  )
}

// ── Video Player ────────────────────────────────────────────────────────────

function LessonVideoPlayer({ lesson }: { lesson: TrainingLesson }) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    if (lesson.file_key) {
      trainingService.getLessonViewUrl(lesson.public_id)
        .then((data) => setUrl(data.url))
        .catch(() => {})
    }
  }, [lesson.public_id, lesson.file_key])

  // YouTube embed
  if (lesson.content && /youtu(be\.com|\.be)/.test(lesson.content)) {
    const match = lesson.content.match(/(?:v=|\.be\/)([a-zA-Z0-9_-]{11})/)
    const videoId = match?.[1]
    if (videoId) {
      return (
        <div className="aspect-video rounded-lg overflow-hidden bg-black">
          <iframe
            src={`https://www.youtube.com/embed/${videoId}`}
            className="w-full h-full"
            allowFullScreen
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          />
        </div>
      )
    }
  }

  // Uploaded video
  if (url) {
    return (
      <div className="aspect-video rounded-lg overflow-hidden bg-black">
        <video src={url} controls className="w-full h-full" />
      </div>
    )
  }

  return <p className="py-8 text-center text-muted-foreground">Video no disponible</p>
}

// ── Certificate status ──────────────────────────────────────────────────────

function CertificateStatus({ programId }: { programId: string }) {
  const [progress, setProgress] = useState<{ is_certified: boolean; certificate_code: string | null } | null>(null)

  useEffect(() => {
    trainingService.getMyPrograms()
      .then((progs) => {
        const found = progs.find((p) => p.program_id === programId)
        if (found) setProgress({ is_certified: found.is_certified, certificate_code: found.certificate_code })
      })
      .catch(() => {})
  }, [programId])

  if (!progress?.is_certified) return null

  return (
    <div className="mx-3 mb-3 rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-800 dark:bg-green-900/20">
      <div className="flex items-center gap-2">
        <Award size={18} className="text-green-600 shrink-0" />
        <div>
          <p className="text-xs font-medium text-green-700 dark:text-green-400">Certificado</p>
          <p className="text-[10px] text-green-600 dark:text-green-500">{progress.certificate_code}</p>
        </div>
      </div>
    </div>
  )
}

// ── Evaluation card ─────────────────────────────────────────────────────────

function EvaluationCard({ evaluation, onSubmissionUpdate }: { evaluation: TrainingEvaluation; onSubmissionUpdate?: (sub: TrainingSubmission) => void }) {
  const [submission, setSubmission] = useState<TrainingSubmission | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [showQuiz, setShowQuiz] = useState(false)
  const [showPractical, setShowPractical] = useState(false)

  useEffect(() => {
    trainingService.getMySubmission(evaluation.public_id)
      .then((s) => { setSubmission(s); setLoaded(true) })
      .catch(() => setLoaded(true))
  }, [evaluation.public_id])

  function handleSubmission(sub: TrainingSubmission) {
    setSubmission(sub)
    onSubmissionUpdate?.(sub)
  }

  const isGraded = submission?.status === 'GRADED'
  const passed = isGraded && submission.score !== null && submission.score >= Math.round(evaluation.passing_score * evaluation.max_score / 100)
  const attemptsUsed = submission?.attempts_used ?? 0
  const canRetry = isGraded && !passed && attemptsUsed < evaluation.max_attempts
  const exhausted = isGraded && !passed && attemptsUsed >= evaluation.max_attempts

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between rounded-lg border bg-card p-4">
        <div>
          <p className="font-medium">{evaluation.title}</p>
          <p className="text-xs text-muted-foreground">
            {evaluation.type === 'QUIZ' ? 'Quiz' : 'Práctica'} · Aprueba con {evaluation.passing_score}/{evaluation.max_score}
          </p>
          {isGraded && (
            <p className={`mt-1 text-sm font-medium ${passed ? 'text-green-600' : 'text-red-600'}`}>
              {submission.score}/{evaluation.max_score} — {passed ? 'Aprobado' : 'No aprobado'}
            </p>
          )}
          {isGraded && (
            <p className="mt-1 text-xs text-muted-foreground">
              Intento {attemptsUsed} de {evaluation.max_attempts}
            </p>
          )}
          {submission?.status === 'SUBMITTED' && (
            <p className="mt-1 text-xs text-yellow-600">Pendiente de calificación</p>
          )}
          {isGraded && submission.feedback && (
            <p className="mt-1 text-xs text-muted-foreground">Feedback: {submission.feedback}</p>
          )}
          {exhausted && (
            <p className="mt-1 text-xs font-medium text-orange-600">
              Agotaste tus intentos — puedes avanzar al siguiente módulo
            </p>
          )}
        </div>
        <div>
          {!submission && evaluation.type === 'QUIZ' && (
            <Button onClick={() => setShowQuiz(true)}>Hacer quiz</Button>
          )}
          {!submission && evaluation.type === 'PRACTICAL' && (
            <Button onClick={() => setShowPractical(true)}>Entregar</Button>
          )}
          {canRetry && evaluation.type === 'QUIZ' && (
            <Button variant="outline" onClick={() => setShowQuiz(true)}>Reintentar quiz</Button>
          )}
          {canRetry && evaluation.type === 'PRACTICAL' && (
            <Button variant="outline" onClick={() => setShowPractical(true)}>Reintentar entrega</Button>
          )}
          {passed && <CheckCircle2 size={24} className="text-green-500" />}
        </div>
      </div>

      <div className="mt-3 rounded-lg border bg-card p-4">
        <RubricEditor
          rubricEndpoint={`/training/evaluations/${evaluation.public_id}/rubric`}
          canEdit={false}
        />
      </div>

      {showQuiz && (
        <QuizModal
          evaluation={evaluation}
          onClose={() => setShowQuiz(false)}
          onSubmitted={(sub) => { handleSubmission(sub); setShowQuiz(false) }}
        />
      )}
      {showPractical && (
        <PracticalModal
          evaluationId={evaluation.public_id}
          onClose={() => setShowPractical(false)}
          onSubmitted={(sub) => { handleSubmission(sub); setShowPractical(false) }}
        />
      )}
    </div>
  )
}

// ── Quiz Modal ──────────────────────────────────────────────────────────────

function QuizModal({ evaluation, onClose, onSubmitted }: {
  evaluation: TrainingEvaluation
  onClose: () => void
  onSubmitted: (s: TrainingSubmission) => void
}) {
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<TrainingSubmission | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    trainingService.listQuestions(evaluation.public_id)
      .then((q) => { setQuestions(q); setLoading(false) })
      .catch(() => setLoading(false))
  }, [evaluation.public_id])

  async function handleSubmit() {
    setError(null); setSubmitting(true)
    try {
      const sub = await trainingService.submitQuiz(evaluation.public_id, answers)
      setResult(sub)
    } catch (err: any) { setError(err?.detail ?? 'Error al enviar') }
    finally { setSubmitting(false) }
  }

  const answeredCount = Object.keys(answers).length
  const totalQuestions = questions.length
  const passed = result?.score !== null && result?.score !== undefined && result.score >= Math.round(evaluation.passing_score * evaluation.max_score / 100)
  const exhausted = result !== null && !passed && result.attempts_used >= evaluation.max_attempts
  const canRetry = result !== null && !passed && !exhausted
  const remainingAttempts = result ? evaluation.max_attempts - result.attempts_used : 0

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/80 p-4">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl bg-card shadow-2xl">
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b px-6 py-4">
          <h2 className="text-lg font-bold">{evaluation.title}</h2>
          <button onClick={() => { if (result) onSubmitted(result); else onClose() }} className="rounded-md p-1 hover:bg-muted">
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading && (
            <div className="flex justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted border-b-primary" />
            </div>
          )}

          {/* Result screen */}
          {result && (
            <div className={`py-8 text-center ${passed ? 'text-green-600' : 'text-destructive'}`}>
              <div className="mb-4 text-6xl">{passed ? '🎉' : '😔'}</div>
              <h3 className="mb-2 text-2xl font-bold">{passed ? '¡Aprobaste!' : 'No aprobaste'}</h3>
              <p className="mb-2 text-4xl font-bold">{result.score}/{evaluation.max_score}</p>
              <p className="mt-2 text-sm text-muted-foreground">
                Intento {result.attempts_used} de {evaluation.max_attempts}
              </p>
              {canRetry && (
                <p className="mt-4 text-sm text-muted-foreground">
                  Necesitas {evaluation.passing_score}/{evaluation.max_score} para aprobar. Te quedan {remainingAttempts} intento{remainingAttempts === 1 ? '' : 's'}.
                </p>
              )}
              {exhausted && (
                <p className="mt-4 text-sm font-medium text-orange-600">
                  Agotaste tus intentos. Puedes avanzar al siguiente módulo.
                </p>
              )}
              <button
                onClick={() => onSubmitted(result)}
                className="mt-6 rounded-lg bg-primary px-6 py-2 font-medium text-primary-foreground hover:bg-primary/90"
              >
                {passed || exhausted ? 'Continuar →' : 'Cerrar'}
              </button>
            </div>
          )}

          {/* Questions */}
          {!loading && !result && (
            <div className="space-y-8">
              {questions.map((q, idx) => (
                <div key={q.public_id}>
                  <p className="mb-3 font-medium">
                    {idx + 1}. {q.question}
                    <span className="ml-2 text-xs text-muted-foreground">({q.points} pts)</span>
                  </p>
                  <div className="space-y-2">
                    {q.options.map((opt) => {
                      const selected = answers[q.public_id] === opt.id
                      return (
                        <label
                          key={opt.id}
                          className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-colors ${
                            selected
                              ? 'border-primary bg-primary/5'
                              : 'hover:bg-muted/50'
                          }`}
                        >
                          <input
                            type="radio"
                            name={q.public_id}
                            checked={selected}
                            onChange={() => setAnswers((prev) => ({ ...prev, [q.public_id]: opt.id }))}
                            className="accent-primary"
                          />
                          <span className="text-sm">{opt.text}</span>
                        </label>
                      )
                    })}
                  </div>
                </div>
              ))}
              {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
            </div>
          )}
        </div>

        {/* Sticky footer */}
        {!loading && !result && (
          <div className="flex shrink-0 items-center justify-between border-t px-6 py-4">
            <span className="text-sm text-muted-foreground">
              {answeredCount} de {totalQuestions} respondidas
            </span>
            <button
              onClick={handleSubmit}
              disabled={answeredCount < totalQuestions || submitting}
              className="rounded-lg bg-primary px-6 py-2 font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              {submitting ? 'Enviando…' : 'Enviar respuestas'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Practical Modal ─────────────────────────────────────────────────────────

function PracticalModal({ evaluationId, onClose, onSubmitted }: {
  evaluationId: string; onClose: () => void; onSubmitted: (s: TrainingSubmission) => void
}) {
  const [content, setContent] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault(); setError(null); setSubmitting(true)
    try {
      const fd = new FormData()
      if (content.trim()) fd.append('content', content.trim())
      if (file) fd.append('file', file)
      const sub = await trainingService.submitPractical(evaluationId, fd)
      onSubmitted(sub)
    } catch (err: any) { setError(err?.detail ?? 'Error al entregar') }
    finally { setSubmitting(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="font-semibold">Entregar evaluación práctica</h3>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X size={16} /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3 px-5 py-4">
          <div className="space-y-1">
            <label className="text-xs font-medium">Respuesta</label>
            <textarea
              className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="Escribe tu respuesta aquí…"
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium">Archivo adjunto</label>
            <input
              type="file"
              className="block w-full text-sm text-muted-foreground file:mr-2 file:rounded file:border-0 file:bg-muted file:px-3 file:py-1.5 file:text-sm file:font-medium"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>Cancelar</Button>
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? 'Entregando…' : 'Entregar'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
