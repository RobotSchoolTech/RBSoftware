'use client'

import { useEffect, useState } from 'react'
import { ChevronRight, FileText, Folder, X } from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/components/ui/use-toast'

export interface RepoPickerFile {
  public_id: string
  name: string
  file_name: string
  file_size?: number | null
  file_type?: string | null
}

interface RepoPickerFolder {
  public_id: string
  name: string
  description?: string | null
  file_count?: number
}

interface Props {
  onClose: () => void
  onSelect: (file: RepoPickerFile) => void
}

/**
 * Navegador del repositorio de documentos para seleccionar un archivo.
 * El backend ya filtra por visibilidad (línea/colegio), así que solo se
 * listan carpetas y archivos que el usuario puede ver.
 */
export function RepositoryPickerModal({ onClose, onSelect }: Props) {
  const [contents, setContents] = useState<{
    subfolders: RepoPickerFolder[]
    files: RepoPickerFile[]
  }>({ subfolders: [], files: [] })
  const [breadcrumb, setBreadcrumb] = useState<RepoPickerFolder[]>([])
  const [loading, setLoading] = useState(true)

  async function loadRoot() {
    setLoading(true)
    try {
      const data = await api.get<RepoPickerFolder[]>('/repository/folders')
      setContents({ subfolders: data, files: [] })
      setBreadcrumb([])
    } catch (err: any) {
      toast({ title: err?.detail ?? 'Error al cargar', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }

  async function openFolder(folder: RepoPickerFolder) {
    setLoading(true)
    try {
      const data = await api.get<{
        subfolders: RepoPickerFolder[]
        files: RepoPickerFile[]
        breadcrumb: RepoPickerFolder[]
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

  return (
    <div className="fixed inset-0 z-[210] flex items-center justify-center bg-black/80 p-4">
      <div className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-xl bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b p-6">
          <h2 className="font-semibold">Seleccionar del repositorio</h2>
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
            contents.files.map((file) => (
              <div
                key={file.public_id}
                className="flex items-center gap-3 rounded-lg border p-3 hover:bg-muted/30"
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-muted">
                  <FileText size={12} className="text-muted-foreground" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{file.name}</p>
                  <p className="truncate text-xs text-muted-foreground">{file.file_name}</p>
                </div>
                <button
                  type="button"
                  onClick={() => onSelect(file)}
                  className="flex shrink-0 items-center gap-1 rounded-lg bg-primary px-3 py-1 text-xs text-white hover:bg-primary/90"
                >
                  Seleccionar
                </button>
              </div>
            ))}

          {!loading &&
            contents.subfolders.length === 0 &&
            contents.files.length === 0 && (
              <p className="py-8 text-center text-sm text-muted-foreground">
                Carpeta vacía
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
