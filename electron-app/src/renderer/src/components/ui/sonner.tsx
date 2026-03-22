import { Toaster as Sonner } from 'sonner'

// Re-export sonner's Toaster for use in the app.
// This replaces the auto-generated shadcn wrapper which had circular imports
// and a next-themes dependency that doesn't apply to Electron.
const Toaster = Sonner

export { Toaster }
