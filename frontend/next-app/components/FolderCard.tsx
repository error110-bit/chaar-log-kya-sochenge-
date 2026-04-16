"use client"

import { Space_Mono } from "next/font/google"

const spaceMono = Space_Mono({ subsets: ["latin"], weight: ["400", "700"] })

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
      <div className="flex items-end gap-1 pl-1">
        {meta.map((item, index) => (
          <div
            key={`${item}-${index}`}
            className={`${spaceMono.className} flex h-8 items-center rounded-t-xl border border-slate-200 border-b-0 bg-white px-3 text-[0.64rem] font-semibold tracking-[0.08em] uppercase text-slate-600 shadow-sm first:bg-[#ff5a1f]/10 first:text-[#ff5a1f]`}
          >
            {item}
          </div>
        ))}
      </div>

      <div className="relative overflow-hidden rounded-tr-2xl rounded-b-2xl border border-slate-200 bg-white p-5 shadow-sm transition group-hover:border-[#ff5a1f] group-hover:shadow-md">
        <div className="absolute right-0 top-0 h-20 w-20 rounded-bl-full bg-[#ff5a1f]/8" />
        <div className="relative z-10 flex min-h-[176px] flex-col justify-between">
          <div>
            <div className="mb-1 flex items-center justify-between gap-3">
              <h3 className="text-[1.05rem] font-semibold tracking-tight text-slate-950">{title}</h3>
              <span className="text-xs text-slate-400 group-hover:text-[#ff5a1f]">open →</span>
            </div>
            <p className="text-sm text-slate-600">{company}</p>
            <p className="mt-3 text-sm leading-6 text-slate-700">{description}</p>
          </div>

          <div className={`${spaceMono.className} mt-5 text-[0.68rem] font-semibold tracking-[0.12em] uppercase text-[#ff5a1f]`}>
            {cta}
          </div>
        </div>
      </div>
    </button>
  )
}
