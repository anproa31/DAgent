import { motion } from 'framer-motion'
import type { ReactNode } from 'react'

interface WizardStepShellProps {
  stepKey: string
  className?: string
  children: ReactNode
}

export function WizardStepShell({
  stepKey,
  className,
  children,
}: WizardStepShellProps) {
  return (
    <motion.div
      key={stepKey}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      className={className}
    >
      {children}
    </motion.div>
  )
}
