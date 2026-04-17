"use client"

import { Cormorant_Garamond, Manrope } from "next/font/google"

const manrope = Manrope({ subsets: ["latin"], weight: ["500", "600", "700"] })
const cormorant = Cormorant_Garamond({ subsets: ["latin"], weight: ["500", "600", "700"] })

function toSentenceCase(value: string) {
  const trimmed = value.trim().toLowerCase()
  if (!trimmed) return value
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1)
}

type FolderCardProps = {
  title: string
  company: string
  meta: string[]
  description: string
  cta: string
  onClick: () => void
}

export function FolderCard({ title, company, meta, description, cta, onClick }: FolderCardProps) {
  return (
    <button
      onClick={onClick}
      className="group flex h-full flex-col text-left transition duration-200 hover:-translate-y-0.5"
    >
      <div className="flex flex-wrap items-end gap-2 pl-1">
        {meta.map((item, index) => (
          <div
            key={`${item}-${index}`}
            className={`${manrope.className} flex h-8 items-center whitespace-nowrap rounded-t-xl border border-stone-300 border-b-0 bg-stone-50 px-3.5 text-[0.68rem] font-semibold leading-none tracking-[0.01em] text-slate-700 shadow-sm first:bg-[var(--accent)]/12 first:text-[var(--accent)]`}
          >
            {item}
          </div>
        ))}
      </div>

      <div className="relative overflow-hidden rounded-tr-2xl rounded-b-2xl border border-stone-300 bg-white p-5 shadow-[0_6px_16px_rgba(30,41,59,0.08)] transition group-hover:border-[var(--accent)] group-hover:shadow-[0_10px_24px_rgba(30,41,59,0.14)]">
        <div className="absolute right-0 top-0 h-20 w-20 rounded-bl-full bg-stone-200/70" />
        <div className="relative z-10 flex min-h-[176px] flex-col justify-between">
          <div>
            <div className="mb-1 flex items-start justify-between gap-3">
              <h3 className={`${cormorant.className} text-[1.55rem] leading-[1.06] tracking-tight text-slate-900`}>{toSentenceCase(title)}</h3>
              <span className={`${manrope.className} inline-flex items-center pt-1 text-[0.72rem] font-medium leading-none tracking-[0.02em] text-slate-500 group-hover:text-[var(--accent)]`}>
                open →
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-600">{toSentenceCase(company)}</p>
            <p className="mt-3 text-sm leading-6 text-slate-700">{description}</p>
          </div>

          <div className={`${manrope.className} mt-5 text-[0.68rem] font-semibold tracking-[0.04em] uppercase text-[var(--accent)]`}>
            {cta}
          </div>
        </div>
      </div>
    </button>
  )
}
