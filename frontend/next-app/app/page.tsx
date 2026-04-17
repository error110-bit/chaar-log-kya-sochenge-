"use client"

import { type CSSProperties, useEffect, useMemo, useState } from "react"
import { Cormorant_Garamond, Manrope } from "next/font/google"
import { FolderCard } from "@/components/FolderCard"
import { fetchInternships, fetchMentorships, type InternshipItem, type MentorshipItem } from "@/lib/opportunity-api"

const manrope = Manrope({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800"] })
const cormorant = Cormorant_Garamond({ subsets: ["latin"], weight: ["500", "600", "700"] })

type StipendFilter = "all" | "unpaid" | "0-5k" | "5-10k" | "10-15k" | "15-20k" | "20k+"
type ModeFilter = "all" | "Remote" | "On-site" | "Hybrid"
type CgpaFilter = "all" | "required" | "none"
type LogoVariant = "A" | "B"
type SitePage = "home" | "internships" | "mentorships"

type ParsedStipend = {
  min: number
  max: number
  isUnpaid: boolean
}

type LoadedInternship = InternshipItem & {
  id: string
  stipendRange: ParsedStipend | null
  hasCgpa: boolean
}

type LoadedMentorship = MentorshipItem & {
  id: string
  hasCgpa: boolean
}

const companies = [
  "Microsoft",
  "Google",
  "Amazon",
  "Razorpay",
  "Morgan Stanley",
  "NVIDIA",
  "Uber",
  "Adobe",
]

const ACTIVE_LOGO_VARIANT: LogoVariant = "A"

const STIPEND_FILTERS: Array<{ id: Exclude<StipendFilter, "all">; label: string }> = [
  { id: "unpaid", label: "Unpaid / not disclosed" },
  { id: "0-5k", label: "0-5k" },
  { id: "5-10k", label: "5-10k" },
  { id: "10-15k", label: "10-15k" },
  { id: "15-20k", label: "15-20k" },
  { id: "20k+", label: "20k+" },
]

const STIPEND_BANDS: Array<{ id: Exclude<StipendFilter, "all" | "unpaid">; label: string; min: number; max: number }> = [
  { id: "0-5k", label: "0-5k", min: 0, max: 5000 },
  { id: "5-10k", label: "5-10k", min: 5000, max: 10000 },
  { id: "10-15k", label: "10-15k", min: 10000, max: 15000 },
  { id: "15-20k", label: "15-20k", min: 15000, max: 20000 },
  { id: "20k+", label: "20k+", min: 20000, max: Number.POSITIVE_INFINITY },
]

const PAGE_THEME: Record<SitePage, { accent: string; pageBg: string; surfaceBg: string; mutedBg: string; headerBg: string }> = {
  home: {
    accent: "#c8652d",
    pageBg: "#fffaf3",
    surfaceBg: "#fffdf8",
    mutedBg: "#f8f3ea",
    headerBg: "rgba(255, 250, 243, 0.95)",
  },
  internships: {
    accent: "#b85d2f",
    pageBg: "#fff9f1",
    surfaceBg: "#fffcf6",
    mutedBg: "#f7efe3",
    headerBg: "rgba(255, 249, 241, 0.95)",
  },
  mentorships: {
    accent: "#2f6f9f",
    pageBg: "#f4f8ff",
    surfaceBg: "#fbfdff",
    mutedBg: "#edf4ff",
    headerBg: "rgba(244, 248, 255, 0.95)",
  },
}

function cleanText(value?: string | null, fallback = "N/A") {
  const trimmed = value?.trim()
  return trimmed ? trimmed : fallback
}

function normalizeCompanyText(value?: string | null) {
  const cleaned = cleanText(value, "").replace(/\s*\d[\d,.]*\s*reviews.*$/i, "").replace(/\s*reviews.*$/i, "")
  return cleaned.replace(/\s+/g, " ").trim()
}

function normalizeReadableText(value: string) {
  return value
    .replace(/([a-zA-Z])(\d)/g, "$1 $2")
    .replace(/(\d)([a-zA-Z])/g, "$1 $2")
    .replace(/(duration|reviews)(?=[a-zA-Z₹\d])/gi, "$1 ")
    .replace(/\s+/g, " ")
    .trim()
}

function normalizeDurationText(value?: string | null) {
  const cleaned = normalizeReadableText(cleanText(value, ""))
  const stripped = cleaned.replace(/\bduration\b/gi, " ").replace(/\bunpaid\b/gi, " ").replace(/\s+/g, " ").trim()
  if (!stripped) return "Not mentioned"
  return stripped.replace(/(\d+)\s*to\s*(\d+)\s*years?/i, "$1-$2 years").replace(/(\d+)\s*to\s*(\d+)\s*months?/i, "$1-$2 months")
}

function normalizeStipendText(value?: string | null): ParsedStipend | null {
  const text = normalizeReadableText(cleanText(value, "")).toLowerCase().replace(/,/g, "")
  if (!text) return null

  if (/unpaid|not disclosed|stipend not mentioned|no stipend/.test(text)) {
    return { min: 0, max: 0, isUnpaid: true }
  }

  const toAmount = (num: string, unit?: string) => {
    const amount = Number.parseFloat(num)
    if (!Number.isFinite(amount)) return null
    const normalizedUnit = (unit ?? "").toLowerCase()
    const multiplier = normalizedUnit === "k" ? 1000 : normalizedUnit === "m" ? 1000000 : normalizedUnit === "l" || normalizedUnit === "lac" || normalizedUnit === "lakh" || normalizedUnit === "lakhs" ? 100000 : 1
    return amount * multiplier
  }

  const amounts: number[] = []

  // Prefer explicit currency/range patterns.
  for (const match of text.matchAll(/(?:₹|inr|rs\.?\s*)\s*(\d+(?:\.\d+)?)(?:\s*(k|m|l|lac|lakh|lakhs))?(?:\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)(?:\s*(k|m|l|lac|lakh|lakhs))?)?/gi)) {
    const first = toAmount(match[1], match[2])
    const second = match[3] ? toAmount(match[3], match[4]) : null
    if (first !== null) amounts.push(first)
    if (second !== null) amounts.push(second)
  }

  // Handle strings like "20000/month" without currency symbol.
  if (amounts.length === 0) {
    for (const match of text.matchAll(/(\d+(?:\.\d+)?)(?:\s*(k|m|l|lac|lakh|lakhs))?\s*(?:\/|per\s*)(?:month|mo)\b/gi)) {
      const amount = toAmount(match[1], match[2])
      if (amount !== null) amounts.push(amount)
    }
  }

  // Final fallback for compact forms like "10k-15k".
  if (amounts.length === 0) {
    for (const match of text.matchAll(/\b(\d+(?:\.\d+)?)(?:\s*(k|m|l|lac|lakh|lakhs))\b/gi)) {
      const amount = toAmount(match[1], match[2])
      if (amount !== null) amounts.push(amount)
    }
  }

  if (amounts.length === 0) return null

  return {
    min: Math.min(...amounts),
    max: Math.max(...amounts),
    isUnpaid: amounts.every((amount) => amount === 0),
  }
}

function normalizeStipendDisplay(value?: string | null) {
  const parsed = normalizeStipendText(value)
  if (!parsed) return normalizeReadableText(cleanText(value))
  if (parsed.isUnpaid) return "Unpaid"

  const min = Math.round(parsed.min)
  const max = Math.round(parsed.max)
  if (min === max) {
    return `₹${min.toLocaleString("en-IN")}/month`
  }

  return `₹${min.toLocaleString("en-IN")} - ₹${max.toLocaleString("en-IN")}/month`
}

function stipendBandForRange(range: ParsedStipend | null): Exclude<StipendFilter, "all" | "unpaid"> | null {
  if (!range || range.isUnpaid) return null
  const midpoint = (range.min + range.max) / 2
  const band = STIPEND_BANDS.find((item) => midpoint >= item.min && midpoint < item.max)
  return band?.id ?? "20k+"
}

function stipendMatchesFilter(range: ParsedStipend | null, filter: StipendFilter) {
  if (filter === "all") return true
  if (filter === "unpaid") return !range || range.isUnpaid
  if (!range || range.isUnpaid) return false

  return stipendBandForRange(range) === filter
}

function formatStipendBadge(range: ParsedStipend | null, raw: string) {
  if (!range) return cleanText(raw)
  if (range.isUnpaid) return "Unpaid"

  const midpoint = (range.min + range.max) / 2
  const band = STIPEND_BANDS.find((item) => midpoint >= item.min && midpoint < item.max)
  return band?.label ?? `${Math.round(range.min / 1000)}k+`
}

function slugify(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")
}

function normalizeMode(value?: string | null): ModeFilter | null {
  const mode = cleanText(value, "").toLowerCase()
  if (!mode) return null
  if (mode.includes("remote") || mode.includes("work from home") || mode.includes("wfh") || mode.includes("online")) return "Remote"
  if (mode.includes("hybrid")) return "Hybrid"
  if (mode.includes("onsite") || mode.includes("on-site") || mode.includes("office") || mode.includes("in-office")) return "On-site"
  return null
}

function hasCgpaRequirement(value?: string | null) {
  const cgpa = cleanText(value, "").toLowerCase()
  if (!cgpa) return false
  return ![
    "no cutoff",
    "not mentioned",
    "not specified",
    "n/a",
    "na",
    "none",
    "any",
  ].some((term) => cgpa.includes(term))
}

function splitBranchTokens(value?: string | null) {
  return cleanText(value, "")
    .split(/[,/]|\band\b/i)
    .map((token) => token.trim())
    .filter((token) => token && !/^(any|n\/a|na|not mentioned|not specified)$/i.test(token))
}

function matchesBranch(value: string, selectedBranch: string) {
  if (selectedBranch === "all") return true
  if (/^(any|n\/a|na)$/i.test(value)) return true
  return value.toLowerCase().includes(selectedBranch.toLowerCase())
}

function stipendBadge(value?: string | null) {
  return formatStipendBadge(normalizeStipendText(value), cleanText(value))
}

function fetchAllPages<T>(fetchPage: (page: number) => Promise<{ meta: { total: number; page_size: number }; data: T[] }>) {
  return fetchPage(1).then(async (firstPage) => {
    const pageSize = firstPage.meta.page_size || 100
    const totalPages = Math.max(1, Math.ceil(firstPage.meta.total / pageSize))

    if (totalPages === 1) {
      return firstPage.data
    }

    const remainingPages = await Promise.all(
      Array.from({ length: totalPages - 1 }, (_, index) => fetchPage(index + 2)),
    )

    return [firstPage.data, ...remainingPages.map((page) => page.data)].flat()
  })
}

function dedupeInternships(items: InternshipItem[]) {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = [cleanText(item.source, ""), normalizeCompanyText(item.company), cleanText(item.title, "")].join("::")
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function dedupeMentorships(items: MentorshipItem[]) {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = [cleanText(item.source, ""), cleanText(item.company, ""), cleanText(item.programme_name, ""), cleanText(item.apply_link, "")].join("::")
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function buildInternshipCard(item: InternshipItem): LoadedInternship {
  const stipend = cleanText(item.stipend)
  const branch = cleanText(item.branch_required)
  const cgpa = cleanText(item.cgpa_required)
  const company = normalizeCompanyText(item.company)
  const title = cleanText(item.title)

  return {
    ...item,
    id: slugify(`${cleanText(item.source, "unknown")}-${company}-${title}-${cleanText(item.apply_link, "no-link")}-${cleanText(item.location, "no-location")}-${cleanText(item.deadline, "no-deadline")}`),
    stipendRange: normalizeStipendText(stipend),
    hasCgpa: hasCgpaRequirement(cgpa),
    source: cleanText(item.source),
    title,
    company,
    location: cleanText(item.location),
    stipend: normalizeStipendDisplay(stipend),
    duration: normalizeDurationText(item.duration),
    mode: cleanText(item.mode),
    internship_type: cleanText(item.internship_type),
    branch_required: branch,
    cgpa_required: cgpa,
    gender: cleanText(item.gender),
    eligibility_raw: cleanText(item.eligibility_raw),
    skills: cleanText(item.skills),
    deadline: cleanText(item.deadline),
    applicants: cleanText(item.applicants),
    apply_link: cleanText(item.apply_link, "#apply"),
  }
}

function buildMentorshipCard(item: MentorshipItem): LoadedMentorship {
  return {
    ...item,
    id: slugify(`${cleanText(item.source, "unknown")}-${item.company}-${item.programme_name}-${cleanText(item.apply_link, "no-link")}`),
    hasCgpa: hasCgpaRequirement(item.cgpa_required),
    source: cleanText(item.source),
    company: cleanText(item.company),
    programme_name: cleanText(item.programme_name),
    programme_type: cleanText(item.programme_type),
    description: cleanText(item.description),
    duration: normalizeDurationText(item.duration),
    mode: cleanText(item.mode),
    eligibility: cleanText(item.eligibility),
    branch_required: cleanText(item.branch_required),
    cgpa_required: cleanText(item.cgpa_required),
    gender: cleanText(item.gender),
    stipend_or_benefits: cleanText(item.stipend_or_benefits),
    deadline: cleanText(item.deadline),
    apply_link: cleanText(item.apply_link, "#apply"),
    how_to_apply: cleanText(item.how_to_apply),
  }
}

function FilterBar({ stipend, setStipend, mode, setMode, cgpa, setCgpa, branch, setBranch, branches, hidePay, onReset, showReset }: { stipend: StipendFilter; setStipend: (v: StipendFilter) => void; mode: ModeFilter; setMode: (v: ModeFilter) => void; cgpa: CgpaFilter; setCgpa: (v: CgpaFilter) => void; branch: string; setBranch: (v: string) => void; branches: string[]; hidePay?: boolean; onReset: () => void; showReset: boolean }) {
  const selectClass = `${manrope.className} h-11 w-[180px] appearance-none rounded-xl border border-stone-200 bg-white px-4 pr-10 text-[0.82rem] font-medium text-slate-700 outline-none shadow-sm transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/15`
  const labelClass = `${manrope.className} mb-1.5 block text-[0.64rem] font-semibold tracking-[0.07em] uppercase text-slate-500`

  return (
    <div className="sticky top-[73px] z-30 border-b border-stone-200 bg-[var(--page-bg)]/95 px-6 py-3 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-end gap-3 rounded-2xl border border-stone-200 bg-[var(--surface-bg)] p-3 shadow-[0_8px_20px_rgba(35,35,35,0.04)] lg:px-4">
        {!hidePay && (
          <div>
            <label className={labelClass} htmlFor="filter-stipend">stipend</label>
            <div className="relative">
              <select
                id="filter-stipend"
                className={selectClass}
                value={stipend}
                onChange={(event) => setStipend(event.target.value as StipendFilter)}
              >
                <option value="all">All</option>
                {STIPEND_FILTERS.map((item) => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </select>
              <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-slate-400">▾</span>
            </div>
          </div>
        )}

        <div>
          <label className={labelClass} htmlFor="filter-mode">mode</label>
          <div className="relative">
            <select
              id="filter-mode"
              className={selectClass}
              value={mode}
              onChange={(event) => setMode(event.target.value as ModeFilter)}
            >
              <option value="all">All</option>
              <option value="Remote">Remote</option>
              <option value="On-site">On-site</option>
              <option value="Hybrid">Hybrid</option>
            </select>
            <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-slate-400">▾</span>
          </div>
        </div>

        <div>
          <label className={labelClass} htmlFor="filter-cgpa">cgpa</label>
          <div className="relative">
            <select
              id="filter-cgpa"
              className={selectClass}
              value={cgpa}
              onChange={(event) => setCgpa(event.target.value as CgpaFilter)}
            >
              <option value="all">All</option>
              <option value="required">Required</option>
              <option value="none">No cutoff</option>
            </select>
            <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-slate-400">▾</span>
          </div>
        </div>

        {branches.length > 0 && (
          <div>
            <label className={labelClass} htmlFor="filter-branch">branch</label>
            <div className="relative">
              <select
                id="filter-branch"
                className={selectClass}
                value={branch}
                onChange={(event) => setBranch(event.target.value)}
              >
                <option value="all">All</option>
                {branches.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
              <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-slate-400">▾</span>
            </div>
          </div>
        )}

        {showReset && (
          <div className="ml-auto">
            <label className={`${labelClass} invisible`} htmlFor="filter-reset">reset</label>
            <button
              id="filter-reset"
              onClick={onReset}
              className={`${manrope.className} h-11 w-[180px] rounded-xl border border-stone-300 bg-white px-4 text-[0.82rem] font-semibold text-slate-700 shadow-sm transition hover:border-[var(--accent)] hover:text-[var(--accent)]`}
            >
              Reset filters
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function EmptyState({ clearFn }: { clearFn: () => void }) {
  return (
    <div className="rounded-2xl border border-dashed border-stone-300 bg-[var(--muted-bg)] py-16 text-center">
      <p className={`${manrope.className} text-[0.75rem] font-semibold tracking-[0.02em] text-slate-500`}>no results match your filters</p>
      <button onClick={clearFn} className="mt-4 text-sm font-medium text-[var(--accent)] underline underline-offset-4">
        clear filters
      </button>
    </div>
  )
}

function SectionHeading({ kicker, title, text }: { kicker: string; title: string; text: string }) {
  return (
    <div className="max-w-3xl">
      <p className={`${manrope.className} text-sm font-bold tracking-[0.08em] uppercase text-[var(--accent)] md:text-base`}>{kicker}</p>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <h2 className={`${cormorant.className} text-4xl leading-[1.06] tracking-tight text-slate-900 md:text-5xl`}>{title}</h2>
      </div>
      <p className="mt-3 text-sm leading-7 text-slate-600 md:text-base">{text}</p>
    </div>
  )
}

function ItGirlsWordmark({ compact = false, variant = ACTIVE_LOGO_VARIANT }: { compact?: boolean; variant?: LogoVariant }) {
  const isMinimal = variant === "B"

  return (
    <div className={`inline-flex items-center rounded-2xl border border-[var(--accent)]/30 bg-[var(--surface-bg)] ${compact ? "px-2.5 py-1.5" : "px-3 py-2"} shadow-[0_6px_16px_rgba(50,28,12,0.08)]`}>
      <div className={`inline-flex items-center ${isMinimal ? "gap-2" : "gap-2.5"}`}>
        {isMinimal ? (
          <span className="relative inline-flex h-8 w-8 items-center justify-center rounded-full border border-[var(--accent)]/35 bg-[var(--muted-bg)] shadow-sm">
            <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent)]" />
            <span className="absolute -right-0.5 top-1.5 h-2 w-2 rounded-full border border-[var(--accent)]/35 bg-[var(--surface-bg)]" />
          </span>
        ) : (
          <span className="relative inline-flex h-8 w-8 items-center justify-center overflow-hidden rounded-lg border border-[var(--accent)]/35 bg-[var(--muted-bg)] shadow-sm">
            <span className="absolute left-0 top-0 h-2.5 w-3.5 rounded-br-md border-r border-b border-[var(--accent)]/35 bg-[var(--surface-bg)]" />
            <span className="h-4 w-4 rounded-full border border-[var(--accent)]/55 bg-[var(--accent)]/12" />
          </span>
        )}

        <span className="flex flex-col leading-none">
          <span className={`${cormorant.className} ${isMinimal ? "text-[1.7rem]" : "text-[1.75rem]"} tracking-tight text-slate-900`}>it girls</span>
        </span>
      </div>
    </div>
  )
}

function DetailsModal({
  open,
  title,
  subtitle,
  rows,
  description,
  ctaLabel,
  ctaLink,
  onClose,
}: {
  open: boolean
  title: string
  subtitle: string
  rows: { label: string; value: string; highlight?: boolean }[]
  description: string
  ctaLabel: string
  ctaLink: string
  onClose: () => void
}) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 px-4 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-2xl rounded-2xl border border-stone-200 bg-[#fffdf8] p-6 shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-4 border-b border-stone-200 pb-4">
          <div>
            <p className={`${manrope.className} text-[0.65rem] font-semibold tracking-[0.04em] uppercase text-[var(--accent)]`}>details</p>
            <h3 className={`${cormorant.className} mt-2 text-3xl leading-[1.06] tracking-tight text-slate-900`}>{title}</h3>
            <p className="mt-1 text-sm text-slate-600">{subtitle}</p>
          </div>
          <button onClick={onClose} className="rounded-full border border-stone-200 px-3 py-1 text-sm text-slate-600 transition hover:border-[var(--accent)] hover:text-[var(--accent)]">
            Close
          </button>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {rows.map((row) => (
            <div key={row.label} className="rounded-xl border border-stone-200 bg-[var(--muted-bg)] p-4">
              <p className={`${manrope.className} text-[0.62rem] font-semibold tracking-[0.04em] uppercase text-slate-500`}>{row.label}</p>
              <p className={`mt-1 text-sm ${row.highlight ? "font-semibold text-slate-950" : "text-slate-800"}`}>{row.value}</p>
            </div>
          ))}
        </div>

        <div className="mt-5 rounded-xl border border-stone-200 bg-white p-4">
          <p className={`${manrope.className} text-[0.62rem] font-semibold tracking-[0.04em] uppercase text-slate-500`}>summary</p>
          <p className="mt-2 text-sm leading-6 text-slate-700">{description}</p>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <a href={ctaLink} target="_blank" rel="noreferrer" className="rounded-full bg-[var(--accent)] px-5 py-2.5 text-sm font-medium text-white transition hover:brightness-95">
            {ctaLabel}
          </a>
          <span className="text-sm text-slate-500">Use this as a starting point for your application.</span>
        </div>
      </div>
    </div>
  )
}

export default function Home() {
  const [page, setPage] = useState<SitePage>("home")
  const [selectedInternship, setSelectedInternship] = useState<LoadedInternship | null>(null)
  const [selectedMentorship, setSelectedMentorship] = useState<LoadedMentorship | null>(null)

  const [internshipItems, setInternshipItems] = useState<LoadedInternship[]>([])
  const [mentorshipItems, setMentorshipItems] = useState<LoadedMentorship[]>([])
  const [internshipLoading, setInternshipLoading] = useState(false)
  const [mentorshipLoading, setMentorshipLoading] = useState(false)
  const [internshipError, setInternshipError] = useState<string | null>(null)
  const [mentorshipError, setMentorshipError] = useState<string | null>(null)

  const [iStipend, setIStipend] = useState<StipendFilter>("all")
  const [iMode, setIMode] = useState<ModeFilter>("all")
  const [iCgpa, setICgpa] = useState<CgpaFilter>("all")
  const [iBranch, setIBranch] = useState("all")

  const [mMode, setMMode] = useState<ModeFilter>("all")
  const [mCgpa, setMCgpa] = useState<CgpaFilter>("all")
  const [mBranch, setMBranch] = useState("all")

  useEffect(() => {
    let cancelled = false

    async function loadInternships() {
      setInternshipLoading(true)
      setInternshipError(null)
      try {
        const items = await fetchAllPages((pageNumber) => fetchInternships({ page: pageNumber, page_size: 100 }))
        if (!cancelled) {
          setInternshipItems(dedupeInternships(items).map(buildInternshipCard))
        }
      } catch (error) {
        if (!cancelled) {
          setInternshipError(error instanceof Error ? error.message : "Failed to load internships.")
        }
      } finally {
        if (!cancelled) {
          setInternshipLoading(false)
        }
      }
    }

    async function loadMentorships() {
      setMentorshipLoading(true)
      setMentorshipError(null)
      try {
        const items = await fetchAllPages((pageNumber) => fetchMentorships({ page: pageNumber, page_size: 100 }))
        if (!cancelled) {
          setMentorshipItems(dedupeMentorships(items).map(buildMentorshipCard))
        }
      } catch (error) {
        if (!cancelled) {
          setMentorshipError(error instanceof Error ? error.message : "Failed to load mentorships.")
        }
      } finally {
        if (!cancelled) {
          setMentorshipLoading(false)
        }
      }
    }

    void loadInternships()
    void loadMentorships()

    return () => {
      cancelled = true
    }
  }, [])

  const internBranches = useMemo(() => {
    const set = new Set<string>()
    internshipItems.forEach((item) => splitBranchTokens(item.branch_required).forEach((branch) => set.add(branch)))
    return Array.from(set)
  }, [internshipItems])

  const mentorBranches = useMemo(() => {
    const set = new Set<string>()
    mentorshipItems.forEach((item) => splitBranchTokens(item.branch_required).forEach((branch) => set.add(branch)))
    return Array.from(set)
  }, [mentorshipItems])

  const filteredInterns = useMemo(() => internshipItems.filter((item) => {
    if (!stipendMatchesFilter(item.stipendRange, iStipend)) return false
    const normalizedMode = normalizeMode(item.mode)
    if (iMode !== "all" && normalizedMode !== iMode) return false
    if (iCgpa === "required" && !item.hasCgpa) return false
    if (iCgpa === "none" && item.hasCgpa) return false
    if (!matchesBranch(item.branch_required, iBranch)) return false
    return true
  }), [internshipItems, iStipend, iMode, iCgpa, iBranch])

  const filteredMentors = useMemo(() => mentorshipItems.filter((item) => {
    const normalizedMode = normalizeMode(item.mode)
    if (mMode !== "all" && normalizedMode !== mMode) return false
    if (mCgpa === "required" && !item.hasCgpa) return false
    if (mCgpa === "none" && item.hasCgpa) return false
    if (!matchesBranch(item.branch_required, mBranch)) return false
    return true
  }), [mentorshipItems, mMode, mCgpa, mBranch])

  const navigate = (nextPage: "home" | "internships" | "mentorships") => {
    setPage(nextPage)
    setSelectedInternship(null)
    setSelectedMentorship(null)
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  const featuredInternships = internshipItems.slice(0, 6)

  const resetInternFilters = () => {
    setIStipend("all")
    setIMode("all")
    setICgpa("all")
    setIBranch("all")
  }

  const resetMentorFilters = () => {
    setMMode("all")
    setMCgpa("all")
    setMBranch("all")
  }

  const hasInternFilters = iStipend !== "all" || iMode !== "all" || iCgpa !== "all" || iBranch !== "all"
  const hasMentorFilters = mMode !== "all" || mCgpa !== "all" || mBranch !== "all"
  const theme = PAGE_THEME[page]

  const pageThemeStyle: CSSProperties = {
    ["--accent" as string]: theme.accent,
    ["--page-bg" as string]: theme.pageBg,
    ["--surface-bg" as string]: theme.surfaceBg,
    ["--muted-bg" as string]: theme.mutedBg,
    ["--header-bg" as string]: theme.headerBg,
  }

  return (
    <div className={`${manrope.className} min-h-screen bg-[var(--page-bg)] text-slate-900 transition-colors duration-300`} style={pageThemeStyle}>
      <header className="sticky top-0 z-40 border-b border-stone-200 bg-[var(--header-bg)] backdrop-blur transition-colors duration-300">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-8">
          <button onClick={() => navigate("home")} className="transition hover:opacity-85">
            <ItGirlsWordmark variant={ACTIVE_LOGO_VARIANT} />
          </button>

          <nav className="inline-flex items-center gap-1 rounded-2xl border border-stone-200 bg-[var(--surface-bg)] p-1 shadow-sm transition-colors duration-300">
            {(["internships", "mentorships"] as const).map((item) => (
              <button
                key={item}
                onClick={() => navigate(item)}
                className={`rounded-xl px-5 py-2.5 text-[0.74rem] font-semibold tracking-[0.08em] uppercase transition ${page === item ? "bg-[var(--accent)] text-white shadow-sm" : "bg-transparent text-slate-600 hover:bg-[var(--muted-bg)] hover:text-[var(--accent)]"}`}
              >
                {item}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {page === "home" && (
        <main>
          <section className="mx-auto max-w-7xl px-6 pb-14 pt-16 lg:px-8 lg:pt-20">
            <div className="max-w-4xl">
              <h1 className={`${cormorant.className} text-5xl leading-[0.95] tracking-tight text-slate-900 md:text-7xl lg:text-8xl`}>
                <span className="block">Build the career</span>
                <span className="block text-[var(--accent)]">They said you couldn&apos;t.</span>
              </h1>
              <p className={`${manrope.className} mt-6 text-[0.78rem] font-semibold tracking-[0.08em] uppercase text-slate-500 md:text-[0.82rem]`}>
                curated internships &amp; mentorships for women in tech &amp; beyond
              </p>
              <p className="mt-5 max-w-2xl text-base leading-7 text-slate-600 md:text-lg">
                Curated opportunities in a cleaner, easier format so you can move faster and apply with less effort.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <a href="#internships" className="rounded-full bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-white transition hover:brightness-95">Browse internships</a>
                <button
                  onClick={() => navigate("mentorships")}
                  className="rounded-full border border-[var(--accent)]/35 bg-[var(--surface-bg)] px-5 py-3 text-sm font-semibold text-[var(--accent)] transition hover:bg-[var(--muted-bg)]"
                >
                  Browse mentorships
                </button>
              </div>
            </div>
          </section>

          <section className="border-y border-stone-200 bg-[var(--muted-bg)] px-6 py-10 lg:px-8">
            <div className="mx-auto max-w-7xl">
              <p className={`${manrope.className} text-sm font-bold tracking-[0.08em] uppercase text-slate-600 md:text-base`}>featured companies</p>
              <div className="mt-5 flex flex-wrap gap-2">
                {companies.map((company) => (
                  <span key={company} className="rounded-full border border-stone-200 bg-[var(--surface-bg)] px-3.5 py-2 text-sm text-slate-700 shadow-sm">
                    {company}
                  </span>
                ))}
              </div>
            </div>
          </section>

          <section id="internships" className="mx-auto max-w-7xl px-6 py-16 lg:px-8">
            <SectionHeading kicker="featured" title="Some of the current internships" text={`A fresh set of opportunities is available right now for you to browse.`} />
            {internshipLoading ? (
              <div className="mt-10 rounded-2xl border border-stone-200 bg-[var(--muted-bg)] py-16 text-center text-sm text-slate-500">Loading internships...</div>
            ) : internshipError ? (
              <div className="mt-10 rounded-2xl border border-red-200 bg-red-50 py-16 text-center text-sm text-red-700">{internshipError}</div>
            ) : (
              <div className="mt-10 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                {featuredInternships.map((intern) => (
                  <FolderCard
                    key={`${intern.id}-${intern.apply_link}`}
                    title={intern.title}
                    company={intern.company}
                    meta={[intern.stipend, intern.duration, intern.location]}
                    description={intern.skills !== "N/A" ? intern.skills : intern.eligibility_raw}
                    cta="Open internship"
                    onClick={() => setSelectedInternship(intern)}
                  />
                ))}
              </div>
            )}
          </section>

          <section className="border-y border-stone-200 bg-[var(--surface-bg)] px-6 py-10 lg:px-8">
            <div className="mx-auto max-w-7xl">
              <p className={`${manrope.className} text-[0.68rem] font-semibold tracking-[0.04em] uppercase text-slate-500`}>what they said</p>
              <div className="mt-6 grid gap-5 md:grid-cols-3">
                {[
                  {
                    quote: "Found my Razorpay internship here within a week. The folder format made it so easy to filter by stipend — I wasn't wasting time on unpaid roles.",
                    author: "Priya M. — IIT Delhi, CSE '25",
                  },
                  {
                    quote: "The mentorship section connected me with a PM at Google who literally changed how I think about my career. I had no idea something like this existed for us.",
                    author: "Anika R. — BITS Pilani, EEE '24",
                  },
                  {
                    quote: "Applied for three internships in one sitting. Everything I needed — branch eligibility, cgpa cutoff, deadline — was right there. No chasing seniors for info.",
                    author: "Sneha T. — NIT Trichy, ECE '25",
                  },
                ].map((item) => (
                  <div key={item.author} className="rounded-2xl border border-stone-200 bg-[var(--muted-bg)] p-6 shadow-sm">
                    <p className="text-sm leading-7 text-slate-700">&quot;{item.quote}&quot;</p>
                    <p className={`${manrope.className} mt-4 text-[0.62rem] font-semibold tracking-[0.04em] uppercase text-[var(--accent)]`}>{item.author}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <footer className="border-t border-stone-200 px-6 py-8 lg:px-8">
            <div className="mx-auto flex max-w-7xl flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <ItGirlsWordmark compact variant={ACTIVE_LOGO_VARIANT} />
              <p className={`${manrope.className} text-[0.64rem] font-semibold tracking-[0.04em] uppercase text-slate-400`}>internships · mentorships</p>
            </div>
          </footer>
        </main>
      )}

      {page === "internships" && (
        <main>
          <section className="mx-auto max-w-7xl px-6 pt-16 lg:px-8 lg:pt-20">
            <div className="max-w-4xl">
              <p className={`${manrope.className} text-sm font-semibold tracking-[0.08em] uppercase text-[var(--accent)] md:text-[0.95rem]`}>internships</p>
              <h1 className={`${cormorant.className} mt-4 text-5xl leading-[1.04] tracking-tight text-slate-900 md:text-6xl`}>All open roles, cleaned up and easy to scan.</h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">Browse the latest internship opportunities with filters that make shortlisting simple.</p>
            </div>
          </section>

          <FilterBar stipend={iStipend} setStipend={setIStipend} mode={iMode} setMode={setIMode} cgpa={iCgpa} setCgpa={setICgpa} branch={iBranch} setBranch={setIBranch} branches={internBranches} onReset={resetInternFilters} showReset={hasInternFilters} />

          <section className="mx-auto max-w-7xl px-6 py-10 lg:px-8">
            {internshipLoading ? (
              <div className="rounded-2xl border border-stone-200 bg-[var(--muted-bg)] py-16 text-center text-sm text-slate-500">Loading internships...</div>
            ) : internshipError ? (
              <div className="rounded-2xl border border-red-200 bg-red-50 py-16 text-center text-sm text-red-700">{internshipError}</div>
            ) : filteredInterns.length === 0 ? (
              <EmptyState clearFn={resetInternFilters} />
            ) : (
              <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                {filteredInterns.map((intern) => (
                  <FolderCard
                    key={`${intern.id}-${intern.apply_link}`}
                    title={intern.title}
                    company={intern.company}
                    meta={[stipendBadge(intern.stipend), intern.duration, intern.location]}
                    description={intern.skills !== "N/A" ? intern.skills : intern.eligibility_raw}
                    cta="Open internship"
                    onClick={() => setSelectedInternship(intern)}
                  />
                ))}
              </div>
            )}
          </section>
        </main>
      )}

      {page === "mentorships" && (
        <main>
          <section className="mx-auto max-w-7xl px-6 pt-16 lg:px-8 lg:pt-20">
            <div className="max-w-4xl">
              <p className={`${manrope.className} text-sm font-semibold tracking-[0.08em] uppercase text-[var(--accent)] md:text-[0.95rem]`}>mentorships</p>
              <h1 className={`${cormorant.className} mt-4 text-5xl leading-[1.04] tracking-tight text-slate-900 md:text-6xl`}>Guidance with structure.</h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">Browse mentorship options designed to help you find the right fit faster.</p>
            </div>
          </section>

          <FilterBar stipend="all" setStipend={() => {}} mode={mMode} setMode={setMMode} cgpa={mCgpa} setCgpa={setMCgpa} branch={mBranch} setBranch={setMBranch} branches={mentorBranches} hidePay onReset={resetMentorFilters} showReset={hasMentorFilters} />

          <section className="mx-auto max-w-7xl px-6 py-10 lg:px-8">
            {mentorshipLoading ? (
              <div className="rounded-2xl border border-stone-200 bg-[var(--muted-bg)] py-16 text-center text-sm text-slate-500">Loading mentorships...</div>
            ) : mentorshipError ? (
              <div className="rounded-2xl border border-red-200 bg-red-50 py-16 text-center text-sm text-red-700">{mentorshipError}</div>
            ) : filteredMentors.length === 0 ? (
              <EmptyState clearFn={resetMentorFilters} />
            ) : (
              <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                {filteredMentors.map((mentorship) => (
                  <FolderCard
                    key={mentorship.id}
                    title={mentorship.programme_name}
                    company={`${mentorship.company} · ${mentorship.programme_type}`}
                    meta={[mentorship.duration, mentorship.mode, mentorship.deadline]}
                    description={mentorship.description}
                    cta="Open mentorship"
                    onClick={() => setSelectedMentorship(mentorship)}
                  />
                ))}
              </div>
            )}
          </section>
        </main>
      )}

      <DetailsModal
        open={selectedInternship !== null}
        title={selectedInternship?.title ?? ""}
        subtitle={selectedInternship?.company ?? ""}
        rows={selectedInternship ? [
          { label: "Source", value: selectedInternship.source },
          { label: "Stipend", value: selectedInternship.stipend, highlight: true },
          { label: "Duration", value: selectedInternship.duration },
          { label: "Location", value: selectedInternship.location },
          { label: "Mode", value: selectedInternship.mode },
          { label: "Type", value: selectedInternship.internship_type },
          { label: "Branch", value: selectedInternship.branch_required },
          { label: "CGPA", value: selectedInternship.cgpa_required },
          { label: "Open to", value: selectedInternship.gender },
          { label: "Deadline", value: selectedInternship.deadline, highlight: true },
        ] : []}
        description={selectedInternship ? (selectedInternship.skills !== "N/A" ? selectedInternship.skills : selectedInternship.eligibility_raw) : ""}
        ctaLabel="Apply now"
        ctaLink={selectedInternship?.apply_link ?? "#"}
        onClose={() => setSelectedInternship(null)}
      />

      <DetailsModal
        open={selectedMentorship !== null}
        title={selectedMentorship?.programme_name ?? ""}
        subtitle={selectedMentorship ? `${selectedMentorship.company} · ${selectedMentorship.programme_type}` : ""}
        rows={selectedMentorship ? [
          { label: "Source", value: selectedMentorship.source },
          { label: "Duration", value: selectedMentorship.duration },
          { label: "Mode", value: selectedMentorship.mode },
          { label: "Branch", value: selectedMentorship.branch_required },
          { label: "CGPA", value: selectedMentorship.cgpa_required },
          { label: "Open to", value: selectedMentorship.gender },
          { label: "Deadline", value: selectedMentorship.deadline, highlight: true },
        ] : []}
        description={selectedMentorship ? selectedMentorship.how_to_apply : ""}
        ctaLabel="Express interest"
        ctaLink={selectedMentorship?.apply_link ?? "#"}
        onClose={() => setSelectedMentorship(null)}
      />
    </div>
  )
}