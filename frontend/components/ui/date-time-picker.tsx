'use client'

import * as React from 'react'
import { CalendarIcon, X } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale/es'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'

interface Props {
  /** Fecha límite como wall-clock local (`YYYY-MM-DDTHH:mm:ss`) o null. */
  value: string | null
  /** Emite wall-clock local o null al limpiar. */
  onChange: (localDateTime: string | null) => void
  /** Si true, no permite elegir días anteriores a hoy (para crear). */
  disablePast?: boolean
  disabled?: boolean
  placeholder?: string
}

/** Serializa un Date a wall-clock local sin zona (misma convención que el
 *  backend guarda para due_date). No usar toISOString(): eso da UTC y descuadra
 *  el round-trip al releer/editar. */
function toLocalNaive(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}:00`
  )
}

/** Combina fecha (calendario) + hora (input) en una sola marca de tiempo,
 *  siempre en hora local. */
export function DateTimePicker({
  value,
  onChange,
  disablePast = false,
  disabled = false,
  placeholder = 'Sin fecha límite',
}: Props) {
  const [open, setOpen] = React.useState(false)
  const current = value ? new Date(value) : null

  // Hora en formato HH:mm para el <input type="time">.
  const timeStr = current ? format(current, 'HH:mm') : '23:59'

  const startOfToday = React.useMemo(() => {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    return d
  }, [])

  function handleDateSelect(day: Date | undefined) {
    if (!day) return
    const [h, m] = timeStr.split(':').map(Number)
    const next = new Date(day)
    next.setHours(h ?? 23, m ?? 59, 0, 0)
    onChange(toLocalNaive(next))
  }

  function handleTimeChange(e: React.ChangeEvent<HTMLInputElement>) {
    // El input de hora está deshabilitado hasta que haya una fecha, así que
    // aquí `current` siempre existe: la hora modifica el día ya elegido.
    if (!current) return
    const [h, m] = e.target.value.split(':').map(Number)
    const next = new Date(current)
    next.setHours(h ?? 0, m ?? 0, 0, 0)
    onChange(toLocalNaive(next))
  }

  return (
    <div className="flex items-center gap-1">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            disabled={disabled}
            className={cn(
              'flex-1 justify-start text-left font-normal',
              !current && 'text-muted-foreground',
            )}
          >
            <CalendarIcon className="mr-2 h-4 w-4 shrink-0" />
            {current ? (
              <span className="truncate">
                {format(current, "d 'de' MMMM yyyy, HH:mm", { locale: es })}
              </span>
            ) : (
              <span>{placeholder}</span>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="flex flex-col">
          <Calendar
            mode="single"
            selected={current ?? undefined}
            onSelect={handleDateSelect}
            defaultMonth={current ?? undefined}
            disabled={disablePast ? { before: startOfToday } : undefined}
            autoFocus
          />
          <div className="flex items-center gap-2 border-t p-3">
            <label className="text-xs font-medium text-muted-foreground">
              Hora
            </label>
            <input
              type="time"
              value={timeStr}
              onChange={handleTimeChange}
              disabled={!current}
              title={!current ? 'Elige primero un día' : undefined}
              className="rounded-md border border-input bg-background px-2 py-1 text-sm disabled:opacity-50"
            />
          </div>
        </PopoverContent>
      </Popover>
      {current && !disabled && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Quitar fecha límite"
          className="h-9 w-9 shrink-0"
          onClick={() => onChange(null)}
        >
          <X className="h-4 w-4" />
        </Button>
      )}
    </div>
  )
}
