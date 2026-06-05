'use client'

import { Menu, X } from 'lucide-react'
import { AuthBootstrap } from '@/components/auth-bootstrap'
import { Nav } from '@/components/nav'
import { Toaster } from '@/components/ui/toaster'
import { useSidebarStore } from '@/lib/store'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { open, collapsed, setOpen, toggleOpen } = useSidebarStore()

  return (
    <div className="flex h-screen overflow-hidden">
      <AuthBootstrap />
      {/* Overlay — mobile only */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      <Nav />

      <main
        className={`flex-1 overflow-y-auto bg-slate-50 dark:bg-background transition-[margin] duration-200 ${
          collapsed ? 'md:ml-16' : 'md:ml-56'
        }`}
      >
        {/* Mobile header with hamburger */}
        <div className="sticky top-0 z-30 flex h-14 items-center border-b bg-background px-4 md:hidden">
          <button
            onClick={toggleOpen}
            className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span className="ml-3 text-sm font-semibold tracking-wide">
            MIEL · RobotSchool
          </span>
        </div>

        <div className="p-6">{children}</div>
      </main>

      <Toaster />
    </div>
  )
}
