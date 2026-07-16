import type { HTMLAttributes } from "react"
export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={`rounded-xl border border-zinc-200 bg-white ${className}`} {...props} /> }
export function CardContent({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={`p-5 ${className}`} {...props} /> }
