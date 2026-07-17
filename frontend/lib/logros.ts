// Los tres logros/ejes de robótica bajo los que se agrupa cada actividad.
// Las claves ASCII casan con el ENUM del backend; las etiquetas son las visibles.

export const LOGROS = ['disenar', 'programar', 'robotizar'] as const
export type Logro = (typeof LOGROS)[number]

export const LOGRO_LABELS: Record<Logro, string> = {
  disenar: 'Diseñar',
  programar: 'Programar',
  robotizar: 'Robotizar',
}

export type NivelLogro = 'excelente' | 'bueno' | 'regular' | 'insuficiente'

export const NIVEL_LABELS: Record<NivelLogro, string> = {
  excelente: 'Excelente',
  bueno: 'Bueno',
  regular: 'Regular',
  insuficiente: 'Insuficiente',
}

// Clases Tailwind para el badge de cada nivel (claro + oscuro).
export const NIVEL_CLASSES: Record<NivelLogro, string> = {
  excelente:
    'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
  bueno: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  regular:
    'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  insuficiente: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
}

export function nivelLabel(level: string | null | undefined): string {
  if (!level) return '—'
  return NIVEL_LABELS[level as NivelLogro] ?? '—'
}
