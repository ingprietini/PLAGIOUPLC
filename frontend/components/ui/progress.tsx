import { clsx } from "clsx"

interface ProgressProps {
  value: number
  className?: string
  variant?: "default" | "success" | "warning" | "danger"
}

export function Progress({ value, className, variant = "default" }: ProgressProps) {
  return (
    <div className={clsx("h-2 w-full overflow-hidden rounded-full bg-gray-100", className)}>
      <div
        className={clsx("h-full rounded-full transition-all duration-500 ease-out progress-bar", {
          "bg-primary-600": variant === "default",
          "bg-green-500": variant === "success",
          "bg-yellow-500": variant === "warning",
          "bg-red-500": variant === "danger",
        })}
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  )
}
