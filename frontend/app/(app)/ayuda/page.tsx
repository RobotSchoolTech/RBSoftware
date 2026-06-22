'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { HelpCircle } from 'lucide-react'
import { useAuthStore } from '@/lib/store'
import { GUIA_DOCENTE, GUIA_ESTUDIANTE } from '@/lib/help-content'

export default function AyudaPage() {
  const { hasRole, isAdmin } = useAuthStore()

  // Precedencia: cualquier rol elevado (docente/director/trainer/admin) ve la
  // guía del docente, que es más completa. Solo el estudiante "puro" ve la suya.
  const esEstudiantePuro =
    hasRole('STUDENT') &&
    !hasRole('TEACHER') &&
    !hasRole('DIRECTOR') &&
    !hasRole('TRAINER') &&
    !hasRole('SUPER_TRAINER') &&
    !isAdmin()

  const guia = esEstudiantePuro ? GUIA_ESTUDIANTE : GUIA_DOCENTE
  const subtitulo = esEstudiantePuro ? 'Guía del estudiante' : 'Guía del docente'

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <header className="mb-8 flex items-center gap-3 border-b border-border pb-6">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <HelpCircle size={24} />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Ayuda</h1>
          <p className="text-sm text-muted-foreground">{subtitulo}</p>
        </div>
      </header>

      <article className="prose prose-sm max-w-none dark:prose-invert prose-headings:font-display prose-headings:text-foreground prose-a:text-primary">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{guia}</ReactMarkdown>
      </article>
    </div>
  )
}
