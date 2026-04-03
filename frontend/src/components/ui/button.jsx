import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // Primary — jewel gradient: primary green → secondary teal
        default:
          "bg-gradient-to-r from-[#006e2a] to-[#006875] text-white shadow-ambient-sm hover:shadow-ambient-md hover:brightness-105 active:brightness-95",
        destructive:
          "bg-destructive text-destructive-foreground shadow-ambient-sm hover:bg-destructive/90",
        outline:
          "bg-surface-container-high text-foreground hover:bg-surface-container-highest",
        // Secondary — surface tonal, no border
        secondary:
          "bg-[#eae7e6] text-[#1c1b1f] hover:bg-[#e4e1e0]",
        // Tertiary — ghost until hover
        ghost:
          "text-foreground hover:bg-[rgba(28,27,31,0.04)]",
        link:
          "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2 rounded-[0.375rem]",
        sm:      "h-8 px-3 text-xs rounded-[0.25rem]",
        lg:      "h-10 px-8 rounded-[0.375rem]",
        icon:    "h-9 w-9 rounded-[0.375rem]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const Button = React.forwardRef(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props} />
  );
})
Button.displayName = "Button"

export { Button, buttonVariants }
