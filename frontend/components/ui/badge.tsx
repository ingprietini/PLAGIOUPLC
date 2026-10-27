import { clsx } from "clsx"

interface BadgeProps {
  variant?: "default" | "success" | "warning" | "danger" | "info"
  children: React.ReactNode
}

export function Badge({ variant = "default", children }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        {
          "bg-gray-100 text-gray-800": variant === "default",
          "bg-green-100 text-green-800": variant === "success",
          "bg-yellow-100 text-yellow-800": variant === "warning",
          "bg-red-100 text-red-800": variant === "danger",
          "bg-blue-100 text-blue-800": variant === "info",
        }
      )}
    >
      {children}
    </span>
  )
}
