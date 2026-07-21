'use client'

import * as React from 'react'
import { CalendarIcon, X } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'

interface Props {
  /** Fecha límite como ISO UTC (lo que guarda el backend) o null. */
  value: string | null
  /** Emite ISO UTC (`Date.toISOString()`) o null al limpiar. */
  onChange: (isoUtc: string | null) => void
  /** Si true, no permite elegir días anteriores a hoy (para crear). */
  disablePast?: boolean
  disabled?: boolean
  placeholder?: string
}

/** Combina fecha (calendario) + hora (input) en una sola marca de tiempo.
 *  El valor viaja y se guarda en UTC; la UI siempre muestra la hora local. */
export function DateTimePicker({
  value,
  onChange,
  disablePast = false,
  disabled = false,
  placeholder = 'Sin fecha límite',
}: Props) {
  const [open, setOpen] = React.useState(false)
  const current = value ? new Date(value) : null

  // Hora en formato HH:mm para el <input type="time">, local al usuario.
  const timeStr = current ? format(current, 'HH:mm') : '23:59'

  const startOfToday = React.useMemo(() => {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    return d
  }, [])

  function emit(next: Date) {
    onChange(next.toISOString())
  }

  function handleDateSelect(day: Date | undefined) {
    if (!day) return
    const [h, m] = timeStr.split(':').map(Number)
    const next = new Date(day)
    next.setHours(h ?? 23, m ?? 59, 0, 0)
    emit(next)
  }

  function handleTimeChange(e: React.ChangeEvent<HTMLInputElement>) {
    const [h, m] = e.target.value.split(':').map(Number)
    // Si aún no hay fecha, ancla en el día seleccionado en el calendario (hoy).
    const base = current ?? new Date()
    const next = new Date(base)
    next.setHours(h ?? 0, m ?? 0, 0, 0)
    emit(next)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          className={cn(
            'w-full justify-start text-left font-normal',
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
          {current && (
            <span
              role="button"
              tabIndex={-1}
              aria-label="Quitar fecha"
              className="ml-auto rounded p-0.5 hover:bg-muted"
              onClick={(e) => {
                e.stopPropagation()
                onChange(null)
              }}
            >
              <X className="h-3.5 w-3.5" />
            </span>
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
            className="rounded-md border border-input bg-background px-2 py-1 text-sm"
          />
        </div>
      </PopoverContent>
    </Popover>
  )
}
