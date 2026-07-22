'use client'

import { useState } from 'react'
import { FolderOpen, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import * as academicService from '@/services/academic'
import {
  RepositoryPickerModal,
  type RepoPickerFile,
} from '@/components/repository/RepositoryPickerModal'

interface Props {
  unitId: string
  onClose: () => void
  onCreated: () => void
}

// 'REPO' no es un tipo real de material: dispara el flujo "tomar del
// repositorio". El backend deduce el tipo final (PDF o FILE) por la extensión.
const TYPE_OPTIONS = [
  { value: 'REPO', label: 'Desde repositorio' },
  { value: 'PDF', label: 'PDF (subir archivo)' },
  { value: 'FILE', label: 'Archivo (código, programación, imagen…)' },
  { value: 'VIDEO', label: 'Video (URL)' },
  { value: 'LINK', label: 'Enlace' },
  { value: 'TEXT', label: 'Texto' },
] as const

// Debe reflejar ALLOWED_MATERIAL_EXTENSIONS del backend. El `accept` es solo una
// guía en el navegador; la whitelist real la valida el backend.
const FILE_ACCEPT =
  '.pdf,.html,.ino,.mblock,.sb3,.py,.txt,.json,.zip,.png,.jpg,.jpeg,.docx,.pptx,.xlsx'

export function AddMaterialModal({ unitId, onClose, onCreated }: Props) {
  const [title, setTitle] = useState('')
  const [type, setType] = useState<string>('REPO')
  const [content, setContent] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [repoFile, setRepoFile] = useState<RepoPickerFile | null>(null)
  const [showPicker, setShowPicker] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function handlePickRepoFile(picked: RepoPickerFile) {
    setRepoFile(picked)
    if (!title.trim()) setTitle(picked.name)
    setShowPicker(false)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      if (type === 'REPO') {
        if (!repoFile) {
          setError('Selecciona un archivo del repositorio')
          setSaving(false)
          return
        }
        await academicService.addMaterialFromRepository(unitId, {
          title: title.trim(),
          file_id: repoFile.public_id,
        })
      } else {
        if ((type === 'PDF' || type === 'FILE') && !file) {
          setError('Selecciona un archivo')
          setSaving(false)
          return
        }
        await academicService.addMaterial(
          unitId,
          {
            title: title.trim(),
            type,
            content:
              type === 'TEXT' || type === 'VIDEO' || type === 'LINK'
                ? content.trim() || null
                : null,
          },
          (type === 'PDF' || type === 'FILE') && file ? file : undefined,
        )
      }
      onCreated()
    } catch (err: any) {
      setError(err?.detail ?? 'Error al agregar material')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      {showPicker && (
        <RepositoryPickerModal
          onClose={() => setShowPicker(false)}
          onSelect={handlePickRepoFile}
        />
      )}
      <div className="w-full max-w-md rounded-lg border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="font-semibold">Agregar material</h3>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-muted">
            <X size={16} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3 px-5 py-4">
          <div className="space-y-1">
            <label className="text-xs font-medium">Tipo</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              {TYPE_OPTIONS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium">Título *</label>
            <Input
              required
              placeholder="Título del material"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          {type === 'REPO' && (
            <div className="space-y-1">
              <label className="text-xs font-medium">Archivo del repositorio</label>
              {repoFile ? (
                <div className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
                  <span className="min-w-0 truncate">
                    {repoFile.name}
                    <span className="ml-1 text-xs text-muted-foreground">
                      ({repoFile.file_name})
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowPicker(true)}
                    className="shrink-0 text-xs text-primary hover:underline"
                  >
                    Cambiar
                  </button>
                </div>
              ) : (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => setShowPicker(true)}
                >
                  <FolderOpen size={14} />
                  <span className="ml-2">Elegir del repositorio</span>
                </Button>
              )}
            </div>
          )}

          {type === 'PDF' && (
            <div className="space-y-1">
              <label className="text-xs font-medium">Archivo PDF</label>
              <input
                type="file"
                accept=".pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="w-full text-sm"
              />
            </div>
          )}

          {type === 'FILE' && (
            <div className="space-y-1">
              <label className="text-xs font-medium">Archivo</label>
              <input
                type="file"
                accept={FILE_ACCEPT}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="w-full text-sm"
              />
              <p className="text-xs text-muted-foreground">
                PDF, HTML, Arduino (.ino), mBlock (.mblock/.sb3), código, imágenes
                y ofimática.
              </p>
            </div>
          )}

          {(type === 'VIDEO' || type === 'LINK') && (
            <div className="space-y-1">
              <label className="text-xs font-medium">URL</label>
              <Input
                placeholder="https://..."
                value={content}
                onChange={(e) => setContent(e.target.value)}
              />
            </div>
          )}
          {type === 'TEXT' && (
            <div className="space-y-1">
              <label className="text-xs font-medium">Contenido</label>
              <textarea
                className="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="Escribe el contenido…"
                value={content}
                onChange={(e) => setContent(e.target.value)}
              />
            </div>
          )}
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
              {saving ? 'Guardando…' : 'Agregar'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
