'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Download,
  Eye,
  File,
  FileImage,
  FileSpreadsheet,
  FileText,
  FileVideo,
  Folder,
  FolderOpen,
  FolderPlus,
  Loader2,
  Lock,
  Search,
  Share2,
  Trash2,
  Upload,
  Users,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useToast } from '@/components/ui/use-toast'
import { FileViewerModal } from '@/components/file-viewer-modal'
import { useAuthStore } from '@/lib/store'
import { api } from '@/lib/api'

// ── Types ────────────────────────────────────────────────────────────────────

interface ShareRead {
  id: number
  scope_type: 'work_line' | 'school'
  work_line: string | null
  school_id: string | null
  school_name: string | null
}

interface FolderRead {
  public_id: string
  name: string
  description: string | null
  parent_id: string | null
  subfolder_count: number
  file_count: number
  created_by_name: string | null
  created_at: string
  updated_at: string
  shares: ShareRead[]
}

interface SchoolOption {
  public_id: string
  name: string
  work_line: string | null
}

interface ShareOptions {
  work_lines: string[]
  schools: SchoolOption[]
}

const WORK_LINE_LABELS: Record<string, string> = {
  robotschool: 'RobotSchool',
  kuntur: 'Kuntur',
  ecua: 'Ecua',
}

interface FileRead {
  public_id: string
  folder_id: string | null
  name: string
  description: string | null
  file_name: string
  file_size: number | null
  file_type: string | null
  uploaded_by_name: string | null
  created_at: string
}

interface BreadcrumbItem {
  public_id: string
  name: string
}

interface FolderDetail {
  public_id: string
  name: string
  description: string | null
  parent_id: string | null
  breadcrumb: BreadcrumbItem[]
  subfolders: FolderRead[]
  files: FileRead[]
  created_by_name: string | null
  created_at: string
  updated_at: string
}

interface SearchResults {
  folders: FolderRead[]
  files: FileRead[]
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatSize(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getFileIcon(fileType: string | null) {
  const t = (fileType ?? '').toLowerCase()
  if (t === 'pdf') return <FileText className="h-5 w-5 text-red-500" />
  if (['doc', 'docx'].includes(t)) return <FileText className="h-5 w-5 text-blue-600" />
  if (['ppt', 'pptx'].includes(t)) return <FileText className="h-5 w-5 text-orange-500" />
  if (['xls', 'xlsx'].includes(t)) return <FileSpreadsheet className="h-5 w-5 text-green-600" />
  if (['png', 'jpg', 'jpeg', 'gif'].includes(t)) return <FileImage className="h-5 w-5 text-purple-500" />
  if (['mp4', 'mov', 'avi'].includes(t)) return <FileVideo className="h-5 w-5 text-indigo-500" />
  return <File className="h-5 w-5 text-gray-400" />
}

function isViewable(fileType: string | null): boolean {
  const t = (fileType ?? '').toLowerCase()
  return t === 'pdf' || ['png', 'jpg', 'jpeg', 'gif'].includes(t)
}

// ── FolderTreeItem ────────────────────────────────────────────────────────────

interface TreeNode {
  folder: FolderRead
  children: TreeNode[]
}

function buildTree(folders: FolderRead[], parentId: string | null = null): TreeNode[] {
  return folders
    .filter((f) => f.parent_id === parentId)
    .map((f) => ({ folder: f, children: buildTree(folders, f.public_id) }))
}

function FolderTreeItem({
  node,
  depth,
  activeFolderId,
  onSelect,
}: {
  node: TreeNode
  depth: number
  activeFolderId: string | null
  onSelect: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const hasChildren = node.children.length > 0 || node.folder.subfolder_count > 0
  const isActive = activeFolderId === node.folder.public_id

  return (
    <div>
      <button
        onClick={() => {
          setOpen((v) => !v)
          onSelect(node.folder.public_id)
        }}
        className={`flex w-full items-center gap-1 rounded px-2 py-1 text-left text-sm transition-colors hover:bg-gray-100 ${
          isActive ? 'bg-indigo-50 font-medium text-indigo-700' : 'text-gray-700'
        }`}
        style={{ paddingLeft: `${8 + depth * 16}px` }}
      >
        {hasChildren ? (
          open ? (
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-gray-400" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-gray-400" />
          )
        ) : (
          <span className="w-3.5" />
        )}
        {open ? (
          <FolderOpen className="h-4 w-4 shrink-0 text-amber-500" />
        ) : (
          <Folder className="h-4 w-4 shrink-0 text-amber-500" />
        )}
        <span className="ml-1 truncate">{node.folder.name}</span>
      </button>
      {open && node.children.length > 0 && (
        <div>
          {node.children.map((child) => (
            <FolderTreeItem
              key={child.folder.public_id}
              node={child}
              depth={depth + 1}
              activeFolderId={activeFolderId}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function RepositoryPage() {
  const { toast } = useToast()
  const { hasRole, isAdmin } = useAuthStore()
  const canManage = isAdmin() || hasRole('TRAINER') || hasRole('SUPER_TRAINER')

  const [rootFolders, setRootFolders] = useState<FolderRead[]>([])
  const [activeFolderId, setActiveFolderId] = useState<string | null>(null)
  const [folderDetail, setFolderDetail] = useState<FolderDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Search
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResults | null>(null)
  const [searching, setSearching] = useState(false)
  const searchTimer = useRef<any>()

  // Modals
  const [showCreateFolder, setShowCreateFolder] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [newFolderDesc, setNewFolderDesc] = useState('')
  const [creatingFolder, setCreatingFolder] = useState(false)

  const [showUpload, setShowUpload] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadName, setUploadName] = useState('')
  const [uploadDesc, setUploadDesc] = useState('')
  const [uploading, setUploading] = useState(false)

  const [viewerOpen, setViewerOpen] = useState(false)
  const [viewerUrl, setViewerUrl] = useState<string | null>(null)
  const [viewerFileName, setViewerFileName] = useState('')
  const [viewerFileType, setViewerFileType] = useState<'PDF' | 'IMAGE'>('PDF')

  // Share modal
  const [shareFolder, setShareFolder] = useState<FolderRead | null>(null)
  const [shareList, setShareList] = useState<ShareRead[]>([])
  const [shareOptions, setShareOptions] = useState<ShareOptions | null>(null)
  const [shareLoading, setShareLoading] = useState(false)
  const [shareSaving, setShareSaving] = useState(false)

  // Load root folders on mount
  const loadRootFolders = useCallback(async () => {
    try {
      const data = await api.get<FolderRead[]>('/repository/folders')
      setRootFolders(data)
    } catch {
      toast({ title: 'Error al cargar carpetas', variant: 'destructive' })
    }
  }, [toast])

  useEffect(() => {
    loadRootFolders()
  }, [loadRootFolders])

  // Load folder detail
  const loadFolder = useCallback(
    async (folderId: string) => {
      setLoadingDetail(true)
      setSearchResults(null)
      setQuery('')
      try {
        const data = await api.get<FolderDetail>(`/repository/folders/${folderId}`)
        setFolderDetail(data)
        setActiveFolderId(folderId)
      } catch {
        toast({ title: 'Error al cargar carpeta', variant: 'destructive' })
      } finally {
        setLoadingDetail(false)
      }
    },
    [toast],
  )

  // Search with debounce
  useEffect(() => {
    if (!query.trim()) {
      setSearchResults(null)
      return
    }
    clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(async () => {
      setSearching(true)
      try {
        const data = await api.get<SearchResults>(`/repository/search?q=${encodeURIComponent(query)}`)
        setSearchResults(data)
      } catch {
        toast({ title: 'Error en la búsqueda', variant: 'destructive' })
      } finally {
        setSearching(false)
      }
    }, 400)
  }, [query, toast])

  // Create folder
  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return
    setCreatingFolder(true)
    try {
      await api.post('/repository/folders', {
        name: newFolderName.trim(),
        description: newFolderDesc.trim() || null,
        parent_id: activeFolderId,
      })
      toast({ title: 'Carpeta creada', variant: 'success' })
      setShowCreateFolder(false)
      setNewFolderName('')
      setNewFolderDesc('')
      await loadRootFolders()
      if (activeFolderId) await loadFolder(activeFolderId)
    } catch {
      toast({ title: 'Error al crear carpeta', variant: 'destructive' })
    } finally {
      setCreatingFolder(false)
    }
  }

  // Delete folder
  const handleDeleteFolder = async (folderId: string) => {
    if (!confirm('¿Eliminar esta carpeta y todo su contenido?')) return
    try {
      await api.delete(`/repository/folders/${folderId}`)
      toast({ title: 'Carpeta eliminada', variant: 'success' })
      if (activeFolderId === folderId) {
        setActiveFolderId(null)
        setFolderDetail(null)
      }
      await loadRootFolders()
    } catch {
      toast({ title: 'Error al eliminar carpeta', variant: 'destructive' })
    }
  }

  // Upload file
  const handleUpload = async () => {
    if (!uploadFile || !uploadName.trim()) return
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', uploadFile)
      formData.append('name', uploadName.trim())
      if (uploadDesc.trim()) formData.append('description', uploadDesc.trim())
      if (activeFolderId) formData.append('folder_id', activeFolderId)
      await api.postForm('/repository/files', formData)
      toast({ title: 'Archivo subido', variant: 'success' })
      setShowUpload(false)
      setUploadFile(null)
      setUploadName('')
      setUploadDesc('')
      if (activeFolderId) await loadFolder(activeFolderId)
    } catch {
      toast({ title: 'Error al subir archivo', variant: 'destructive' })
    } finally {
      setUploading(false)
    }
  }

  // Delete file
  const handleDeleteFile = async (fileId: string) => {
    if (!confirm('¿Eliminar este archivo?')) return
    try {
      await api.delete(`/repository/files/${fileId}`)
      toast({ title: 'Archivo eliminado', variant: 'success' })
      if (activeFolderId) await loadFolder(activeFolderId)
    } catch {
      toast({ title: 'Error al eliminar archivo', variant: 'destructive' })
    }
  }

  // View file
  const handleView = async (file: FileRead) => {
    try {
      const data = await api.get<{ url: string; file_name: string; file_type: string }>(
        `/repository/files/${file.public_id}/view`,
      )
      const ft = (data.file_type ?? '').toLowerCase()
      setViewerUrl(data.url)
      setViewerFileName(data.file_name)
      setViewerFileType(['png', 'jpg', 'jpeg', 'gif'].includes(ft) ? 'IMAGE' : 'PDF')
      setViewerOpen(true)
    } catch {
      toast({ title: 'Error al abrir archivo', variant: 'destructive' })
    }
  }

  // Download file
  const handleDownload = async (file: FileRead) => {
    try {
      const data = await api.get<{ url: string; file_name: string }>(
        `/repository/files/${file.public_id}/download`,
      )
      const a = document.createElement('a')
      a.href = data.url
      a.download = data.file_name
      a.click()
    } catch {
      toast({ title: 'Error al descargar archivo', variant: 'destructive' })
    }
  }

  // Share: open modal + load options/current shares
  const handleOpenShare = async (folder: FolderRead) => {
    setShareFolder(folder)
    setShareLoading(true)
    try {
      const [opts, shares] = await Promise.all([
        shareOptions
          ? Promise.resolve(shareOptions)
          : api.get<ShareOptions>('/repository/share-options'),
        api.get<ShareRead[]>(`/repository/folders/${folder.public_id}/shares`),
      ])
      setShareOptions(opts)
      setShareList(shares)
    } catch {
      toast({ title: 'Error al cargar compartición', variant: 'destructive' })
      setShareFolder(null)
    } finally {
      setShareLoading(false)
    }
  }

  const refreshAfterShareChange = async () => {
    await loadRootFolders()
    if (activeFolderId) await loadFolder(activeFolderId)
  }

  const handleAddShare = async (
    payload: { scope_type: 'work_line'; work_line: string } | { scope_type: 'school'; school_id: string },
  ) => {
    if (!shareFolder) return
    setShareSaving(true)
    try {
      await api.post(`/repository/folders/${shareFolder.public_id}/shares`, payload)
      const shares = await api.get<ShareRead[]>(
        `/repository/folders/${shareFolder.public_id}/shares`,
      )
      setShareList(shares)
      await refreshAfterShareChange()
    } catch (e: any) {
      const msg = e?.status === 409 ? 'Esa compartición ya existe' : 'Error al compartir'
      toast({ title: msg, variant: 'destructive' })
    } finally {
      setShareSaving(false)
    }
  }

  const handleRemoveShare = async (shareId: number) => {
    if (!shareFolder) return
    setShareSaving(true)
    try {
      await api.delete(`/repository/folders/${shareFolder.public_id}/shares/${shareId}`)
      setShareList((prev) => prev.filter((s) => s.id !== shareId))
      await refreshAfterShareChange()
    } catch {
      toast({ title: 'Error al quitar compartición', variant: 'destructive' })
    } finally {
      setShareSaving(false)
    }
  }

  const tree = buildTree(rootFolders)

  const displayFiles: FileRead[] = searchResults
    ? searchResults.files
    : folderDetail?.files ?? []

  const displayFolders: FolderRead[] = searchResults
    ? searchResults.folders
    : folderDetail?.subfolders ?? []

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden">
      {/* Sidebar */}
      <aside className="flex w-64 shrink-0 flex-col border-r border-gray-200 bg-white">
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <span className="text-sm font-semibold text-gray-700">Carpetas</span>
          {canManage && (
            <button
              onClick={() => {
                setActiveFolderId(null)
                setShowCreateFolder(true)
              }}
              className="rounded p-1 hover:bg-gray-100"
              title="Nueva carpeta raíz"
            >
              <FolderPlus className="h-4 w-4 text-gray-500" />
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto py-2">
          {tree.length === 0 && (
            <p className="px-4 py-6 text-center text-xs text-gray-400">Sin carpetas</p>
          )}
          {tree.map((node) => (
            <FolderTreeItem
              key={node.folder.public_id}
              node={node}
              depth={0}
              activeFolderId={activeFolderId}
              onSelect={loadFolder}
            />
          ))}
        </div>
      </aside>

      {/* Main */}
      <main className="flex flex-1 flex-col overflow-hidden bg-gray-50">
        {/* Toolbar */}
        <div className="flex items-center gap-3 border-b border-gray-200 bg-white px-6 py-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar carpetas y archivos..."
              className="pl-9 text-sm"
            />
            {searching && (
              <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-gray-400" />
            )}
          </div>
          {canManage && (
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setShowCreateFolder(true)}
                className="gap-1"
              >
                <FolderPlus className="h-4 w-4" />
                Carpeta
              </Button>
              <Button
                size="sm"
                onClick={() => setShowUpload(true)}
                className="gap-1 bg-[#1A237E] hover:bg-[#283593]"
              >
                <Upload className="h-4 w-4" />
                Subir archivo
              </Button>
            </div>
          )}
        </div>

        {/* Breadcrumb */}
        {!searchResults && folderDetail && (
          <div className="flex items-center gap-1 border-b border-gray-100 bg-white px-6 py-2 text-sm text-gray-500">
            <button
              onClick={() => {
                setActiveFolderId(null)
                setFolderDetail(null)
              }}
              className="hover:text-indigo-600"
            >
              Inicio
            </button>
            {folderDetail.breadcrumb.map((crumb) => (
              <span key={crumb.public_id} className="flex items-center gap-1">
                <ChevronRight className="h-3.5 w-3.5" />
                <button
                  onClick={() => loadFolder(crumb.public_id)}
                  className="hover:text-indigo-600"
                >
                  {crumb.name}
                </button>
              </span>
            ))}
          </div>
        )}

        {searchResults && (
          <div className="flex items-center gap-2 border-b border-gray-100 bg-white px-6 py-2 text-sm text-gray-500">
            <span>Resultados para &quot;{query}&quot;</span>
            <button
              onClick={() => {
                setQuery('')
                setSearchResults(null)
              }}
              className="ml-2 rounded-full p-0.5 hover:bg-gray-100"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loadingDetail && (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          )}

          {!loadingDetail && !activeFolderId && !searchResults && (
            <div className="mb-6">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
                Carpetas raíz
              </h2>
              {rootFolders.length === 0 ? (
                <p className="text-sm text-gray-400">
                  {canManage ? 'Crea una carpeta para comenzar.' : 'No hay carpetas disponibles.'}
                </p>
              ) : (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  {rootFolders.map((f) => (
                    <FolderCard
                      key={f.public_id}
                      folder={f}
                      canManage={canManage}
                      onOpen={() => loadFolder(f.public_id)}
                      onDelete={() => handleDeleteFolder(f.public_id)}
                      onShare={canManage ? () => handleOpenShare(f) : undefined}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {!loadingDetail && (displayFolders.length > 0 || (activeFolderId && !searchResults)) && (
            <div className="mb-6">
              {displayFolders.length > 0 && (
                <>
                  <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
                    {searchResults ? 'Carpetas' : 'Subcarpetas'}
                  </h2>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                    {displayFolders.map((f) => (
                      <FolderCard
                        key={f.public_id}
                        folder={f}
                        canManage={canManage}
                        onOpen={() => loadFolder(f.public_id)}
                        onDelete={() => handleDeleteFolder(f.public_id)}
                        onShare={canManage ? () => handleOpenShare(f) : undefined}
                      />
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {!loadingDetail && displayFiles.length > 0 && (
            <div>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
                {searchResults ? 'Archivos' : 'Archivos'}
              </h2>
              <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
                {displayFiles.map((file, idx) => (
                  <FileRow
                    key={file.public_id}
                    file={file}
                    canManage={canManage}
                    isLast={idx === displayFiles.length - 1}
                    onView={() => handleView(file)}
                    onDownload={() => handleDownload(file)}
                    onDelete={() => handleDeleteFile(file.public_id)}
                  />
                ))}
              </div>
            </div>
          )}

          {!loadingDetail &&
            !searchResults &&
            activeFolderId &&
            displayFolders.length === 0 &&
            displayFiles.length === 0 && (
              <p className="mt-8 text-center text-sm text-gray-400">Carpeta vacía</p>
            )}
        </div>
      </main>

      {/* Create folder modal */}
      {showCreateFolder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-semibold text-gray-800">Nueva carpeta</h3>
              <button onClick={() => setShowCreateFolder(false)}>
                <X className="h-5 w-5 text-gray-400" />
              </button>
            </div>
            <div className="space-y-3">
              <Input
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                placeholder="Nombre de la carpeta"
                autoFocus
              />
              <Input
                value={newFolderDesc}
                onChange={(e) => setNewFolderDesc(e.target.value)}
                placeholder="Descripción (opcional)"
              />
              {activeFolderId && folderDetail && (
                <p className="text-xs text-gray-500">
                  Dentro de: <span className="font-medium">{folderDetail.name}</span>
                </p>
              )}
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowCreateFolder(false)}>
                Cancelar
              </Button>
              <Button
                size="sm"
                onClick={handleCreateFolder}
                disabled={creatingFolder || !newFolderName.trim()}
                className="bg-[#1A237E] hover:bg-[#283593]"
              >
                {creatingFolder ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Crear'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Upload file modal */}
      {showUpload && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-semibold text-gray-800">Subir archivo</h3>
              <button onClick={() => setShowUpload(false)}>
                <X className="h-5 w-5 text-gray-400" />
              </button>
            </div>
            <div className="space-y-3">
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-gray-600">Archivo</span>
                <input
                  type="file"
                  accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.png,.jpg,.jpeg,.gif,.mp4,.mov,.avi"
                  onChange={(e) => {
                    const f = e.target.files?.[0] ?? null
                    setUploadFile(f)
                    if (f && !uploadName) setUploadName(f.name.replace(/\.[^.]+$/, ''))
                  }}
                  className="block w-full text-sm text-gray-500 file:mr-3 file:rounded file:border-0 file:bg-indigo-50 file:px-3 file:py-1 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100"
                />
              </label>
              <Input
                value={uploadName}
                onChange={(e) => setUploadName(e.target.value)}
                placeholder="Nombre del archivo"
              />
              <Input
                value={uploadDesc}
                onChange={(e) => setUploadDesc(e.target.value)}
                placeholder="Descripción (opcional)"
              />
              {activeFolderId && folderDetail && (
                <p className="text-xs text-gray-500">
                  En: <span className="font-medium">{folderDetail.name}</span>
                </p>
              )}
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowUpload(false)}>
                Cancelar
              </Button>
              <Button
                size="sm"
                onClick={handleUpload}
                disabled={uploading || !uploadFile || !uploadName.trim()}
                className="bg-[#1A237E] hover:bg-[#283593]"
              >
                {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Subir'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* File viewer */}
      <FileViewerModal
        isOpen={viewerOpen}
        onClose={() => setViewerOpen(false)}
        fileName={viewerFileName}
        fileType={viewerFileType}
        localUrl={viewerUrl}
      />

      {/* Share folder modal */}
      {shareFolder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-800">Compartir carpeta</h3>
                <p className="mt-0.5 text-xs text-gray-500">{shareFolder.name}</p>
              </div>
              <button onClick={() => setShareFolder(null)}>
                <X className="h-5 w-5 text-gray-400" />
              </button>
            </div>
            {shareLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
              </div>
            ) : (
              <>
                <div className="mb-4">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                    Compartida con
                  </p>
                  {shareList.length === 0 ? (
                    <p className="flex items-center gap-1.5 text-sm text-gray-400">
                      <Lock className="h-3.5 w-3.5" />
                      Privada — solo tú y los administradores la ven.
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {shareList.map((share) => (
                        <span
                          key={share.id}
                          className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700"
                        >
                          {share.scope_type === 'work_line'
                            ? (WORK_LINE_LABELS[share.work_line ?? ''] ?? share.work_line)
                            : share.school_name}
                          <button
                            onClick={() => handleRemoveShare(share.id)}
                            disabled={shareSaving}
                            className="ml-0.5 rounded-full p-0.5 hover:bg-indigo-100 disabled:opacity-50"
                          >
                            <X className="h-2.5 w-2.5" />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <AddShareForm
                  shareOptions={shareOptions}
                  onAdd={handleAddShare}
                  saving={shareSaving}
                />
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── AddShareForm ──────────────────────────────────────────────────────────────

function AddShareForm({
  shareOptions,
  onAdd,
  saving,
}: {
  shareOptions: ShareOptions | null
  onAdd: (
    payload:
      | { scope_type: 'work_line'; work_line: string }
      | { scope_type: 'school'; school_id: string },
  ) => void
  saving: boolean
}) {
  const [scopeType, setScopeType] = useState<'work_line' | 'school'>('work_line')
  const [workLine, setWorkLine] = useState('')
  const [schoolId, setSchoolId] = useState('')

  const canSubmit = !saving && (scopeType === 'work_line' ? !!workLine : !!schoolId)

  const handleSubmit = () => {
    if (scopeType === 'work_line' && workLine) {
      onAdd({ scope_type: 'work_line', work_line: workLine })
      setWorkLine('')
    } else if (scopeType === 'school' && schoolId) {
      onAdd({ scope_type: 'school', school_id: schoolId })
      setSchoolId('')
    }
  }

  return (
    <div className="border-t border-gray-100 pt-4">
      <p className="mb-3 text-xs font-medium uppercase tracking-wide text-gray-500">
        Agregar acceso
      </p>
      <div className="mb-3 flex gap-2">
        {(['work_line', 'school'] as const).map((type) => (
          <button
            key={type}
            onClick={() => {
              setScopeType(type)
              setWorkLine('')
              setSchoolId('')
            }}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              scopeType === type
                ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                : 'border-gray-200 text-gray-600 hover:border-indigo-300'
            }`}
          >
            {type === 'work_line' ? 'Línea de trabajo' : 'Colegio'}
          </button>
        ))}
      </div>
      {scopeType === 'work_line' ? (
        <div className="flex flex-wrap gap-2">
          {shareOptions?.work_lines.map((wl) => (
            <button
              key={wl}
              onClick={() => setWorkLine(wl === workLine ? '' : wl)}
              className={`rounded border px-3 py-1.5 text-xs transition-colors ${
                workLine === wl
                  ? 'border-indigo-600 bg-indigo-600 text-white'
                  : 'border-gray-200 text-gray-600 hover:border-indigo-300'
              }`}
            >
              {WORK_LINE_LABELS[wl] ?? wl}
            </button>
          ))}
        </div>
      ) : (
        <select
          value={schoolId}
          onChange={(e) => setSchoolId(e.target.value)}
          className="w-full rounded border border-gray-200 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none"
        >
          <option value="">Seleccionar colegio...</option>
          {shareOptions?.schools.map((s) => (
            <option key={s.public_id} value={s.public_id}>
              {s.name}
              {s.work_line ? ` · ${WORK_LINE_LABELS[s.work_line] ?? s.work_line}` : ''}
            </option>
          ))}
        </select>
      )}
      <div className="mt-3 flex justify-end">
        <Button
          size="sm"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="bg-[#1A237E] hover:bg-[#283593]"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Agregar acceso'}
        </Button>
      </div>
    </div>
  )
}

// ── FolderCard ─────────────────────────────────────────────────────────────────

function FolderCard({
  folder,
  canManage,
  onOpen,
  onDelete,
  onShare,
}: {
  folder: FolderRead
  canManage: boolean
  onOpen: () => void
  onDelete: () => void
  onShare?: () => void
}) {
  return (
    <div className="group relative flex flex-col rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md">
      <button onClick={onOpen} className="flex flex-col items-start gap-2 text-left">
        <div className="flex items-center gap-2">
          <Folder className="h-8 w-8 text-amber-400" />
          {folder.shares.length === 0 && <Lock className="h-3 w-3 text-gray-300" title="Privada" />}
        </div>
        <span className="line-clamp-2 text-sm font-medium text-gray-800">{folder.name}</span>
        <span className="text-xs text-gray-400">
          {folder.subfolder_count} subcarpetas · {folder.file_count} archivos
        </span>
        {folder.shares.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {folder.shares.map((s) => (
              <span
                key={s.id}
                className="inline-block rounded-full bg-indigo-50 px-2 py-0.5 text-xs text-indigo-600"
              >
                {s.scope_type === 'work_line'
                  ? (WORK_LINE_LABELS[s.work_line ?? ''] ?? s.work_line)
                  : s.school_name}
              </span>
            ))}
          </div>
        )}
      </button>
      {canManage && (
        <div className="absolute right-2 top-2 hidden items-center gap-0.5 group-hover:flex">
          {onShare && (
            <button
              onClick={(e) => { e.stopPropagation(); onShare() }}
              className="rounded p-1 hover:bg-indigo-50"
              title="Compartir"
            >
              <Users className="h-3.5 w-3.5 text-indigo-400" />
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onDelete() }}
            className="rounded p-1 hover:bg-red-50"
            title="Eliminar"
          >
            <Trash2 className="h-3.5 w-3.5 text-red-400" />
          </button>
        </div>
      )}
    </div>
  )
}

// ── FileRow ───────────────────────────────────────────────────────────────────

function FileRow({
  file,
  canManage,
  isLast,
  onView,
  onDownload,
  onDelete,
}: {
  file: FileRead
  canManage: boolean
  isLast: boolean
  onView: () => void
  onDownload: () => void
  onDelete: () => void
}) {
  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 ${!isLast ? 'border-b border-gray-100' : ''}`}
    >
      <div className="shrink-0">{getFileIcon(file.file_type)}</div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-gray-800">{file.name}</p>
        <p className="text-xs text-gray-400">
          {file.file_name}
          {file.file_size ? ` · ${formatSize(file.file_size)}` : ''}
          {file.uploaded_by_name ? ` · ${file.uploaded_by_name}` : ''}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {isViewable(file.file_type) && (
          <button
            onClick={onView}
            className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-indigo-600"
            title="Ver"
          >
            <Eye className="h-4 w-4" />
          </button>
        )}
        <button
          onClick={onDownload}
          className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-indigo-600"
          title="Descargar"
        >
          <Download className="h-4 w-4" />
        </button>
        {canManage && (
          <button
            onClick={onDelete}
            className="rounded p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500"
            title="Eliminar"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  )
}
