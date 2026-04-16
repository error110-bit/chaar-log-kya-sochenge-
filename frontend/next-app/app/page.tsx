"use client"

import { useEffect, useMemo, useState } from "react"
import Image from "next/image"
import { Inter, Space_Mono } from "next/font/google"
import { FolderCard } from "@/components/FolderCard"
import { fetchInternships, fetchMentorships, type InternshipItem, type MentorshipItem } from "@/lib/opportunity-api"

const inter = Inter({ subsets: ["latin"], weight: ["400", "500", "600", "700"] })
const spaceMono = Space_Mono({ subsets: ["latin"], weight: ["400", "700"] })

type StipendFilter = "all" | "high" | "mid" | "low"
type ModeFilter = "all" | "Remote" | "On-site" | "Hybrid"
type CgpaFilter = "all" | "required" | "none"

type LoadedInternship = InternshipItem & {
  id: string
  stipendTier: StipendFilter | null
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

function cleanText(value?: string | null, fallback = "N/A") {
  const trimmed = value?.trim()
  return trimmed ? trimmed : fallback
}

function slugify(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")
}

function initials(value: string) {
  const parts = value.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "OP"
  return parts.map((part) => part[0]).join("").slice(0, 3).toUpperCase()
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

function extractStipendAmount(value?: string | null) {
  const stipend = cleanText(value, "").toLowerCase()
  if (!stipend || stipend.includes("not disclosed") || stipend.includes("n/a") || stipend.includes("na")) return null

  const match = stipend.match(/₹\s*([\d,]+(?:\.\d+)?)\s*(k|m|l|lac|lakh|lakhs)?/i) ?? stipend.match(/([\d,]+(?:\.\d+)?)\s*(k|m|l|lac|lakh|lakhs)?/i)
  if (!match) return null

  const amount = Number.parseFloat(match[1].replace(/,/g, ""))
  if (!Number.isFinite(amount)) return null

  const unit = (match[2] ?? "").toLowerCase()
  const multiplier = unit === "k" ? 1000 : unit === "m" ? 1000000 : unit === "l" || unit === "lac" || unit === "lakh" || unit === "lakhs" ? 100000 : 1
  return amount * multiplier
}

function classifyStipend(value?: string | null): StipendFilter | null {
  const amount = extractStipendAmount(value)
  if (amount === null) return null
  if (amount >= 50000) return "high"
  if (amount >= 15000) return "mid"
  return "low"
}

function stipendBadge(value?: string | null) {
  const amount = extractStipendAmount(value)
  if (amount === null) return cleanText(value)
  if (amount >= 50000) return "₹₹₹"
  if (amount >= 15000) return "₹₹"
  return "₹"
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
    const key = [cleanText(item.source, ""), cleanText(item.company, ""), cleanText(item.title, ""), cleanText(item.apply_link, "")].join("::")
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

  return {
    ...item,
    id: slugify(`${cleanText(item.source, "unknown")}-${item.company}-${item.title}-${cleanText(item.apply_link, "no-link")}`),
    stipendTier: classifyStipend(stipend),
    hasCgpa: hasCgpaRequirement(cgpa),
    source: cleanText(item.source),
    title: cleanText(item.title),
    company: cleanText(item.company),
    location: cleanText(item.location),
    stipend,
    duration: cleanText(item.duration),
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
    duration: cleanText(item.duration),
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

function FilterBar({ stipend, setStipend, mode, setMode, cgpa, setCgpa, branch, setBranch, branches, hidePay }: { stipend: StipendFilter; setStipend: (v: StipendFilter) => void; mode: ModeFilter; setMode: (v: ModeFilter) => void; cgpa: CgpaFilter; setCgpa: (v: CgpaFilter) => void; branch: string; setBranch: (v: string) => void; branches: string[]; hidePay?: boolean }) {
  const chipBase = `${spaceMono.className} rounded-full border px-3 py-1.5 text-[0.62rem] tracking-[0.08em] transition`
  const active = "border-[#ff5a1f] bg-[#ff5a1f] text-white"
  const inactive = "border-slate-200 bg-white text-slate-600 hover:border-[#ff5a1f] hover:text-[#ff5a1f]"

  return (
    <div className="sticky top-[73px] z-30 border-b border-slate-200 bg-white/95 px-6 py-3 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-5 gap-y-3 lg:px-2">
        {!hidePay && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className={`${spaceMono.className} mr-1 text-[0.56rem] font-semibold tracking-[0.12em] uppercase text-slate-500`}>stipend</span>
            {(["all", "high", "mid", "low"] as StipendFilter[]).map((value) => (
              <button key={value} className={`${chipBase} ${stipend === value ? active : inactive}`} onClick={() => setStipend(value)}>
                {value === "all" ? "all" : value === "high" ? "₹₹₹ high" : value === "mid" ? "₹₹ mid" : "₹ low"}
              </button>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-1.5">
          <span className={`${spaceMono.className} mr-1 text-[0.56rem] font-semibold tracking-[0.12em] uppercase text-slate-500`}>mode</span>
          {(["all", "Remote", "On-site", "Hybrid"] as ModeFilter[]).map((value) => (
            <button key={value} className={`${chipBase} ${mode === value ? active : inactive}`} onClick={() => setMode(value)}>
              {value === "all" ? "all" : value.toLowerCase()}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <span className={`${spaceMono.className} mr-1 text-[0.56rem] font-semibold tracking-[0.12em] uppercase text-slate-500`}>cgpa</span>
          {(["all", "required", "none"] as CgpaFilter[]).map((value) => (
            <button key={value} className={`${chipBase} ${cgpa === value ? active : inactive}`} onClick={() => setCgpa(value)}>
              {value === "all" ? "all" : value === "required" ? "required" : "no cutoff"}
            </button>
          ))}
        </div>

        {branches.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className={`${spaceMono.className} mr-1 text-[0.56rem] font-semibold tracking-[0.12em] uppercase text-slate-500`}>branch</span>
            <button className={`${chipBase} ${branch === "all" ? active : inactive}`} onClick={() => setBranch("all")}>all</button>
            {branches.map((item) => (
              <button key={item} className={`${chipBase} ${branch === item ? active : inactive}`} onClick={() => setBranch(item)}>
                {item}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function EmptyState({ clearFn }: { clearFn: () => void }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 py-16 text-center">
      <p className={`${spaceMono.className} text-[0.75rem] font-semibold tracking-[0.12em] uppercase text-slate-500`}>no results match your filters</p>
      <button onClick={clearFn} className="mt-4 text-sm font-medium text-[#ff5a1f] underline underline-offset-4">
        clear filters
      </button>
    </div>
  )
}

function SectionHeading({ kicker, title, text }: { kicker: string; title: string; text: string }) {
  return (
    <div className="max-w-3xl">
      <p className={`${spaceMono.className} text-[0.68rem] font-semibold tracking-[0.16em] uppercase text-[#ff5a1f]`}>{kicker}</p>
      <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950 md:text-4xl">{title}</h2>
      <p className="mt-3 text-sm leading-7 text-slate-600 md:text-base">{text}</p>
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
      <div className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-4">
          <div>
            <p className={`${spaceMono.className} text-[0.65rem] font-semibold tracking-[0.14em] uppercase text-[#ff5a1f]`}>details</p>
            <h3 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{title}</h3>
            <p className="mt-1 text-sm text-slate-600">{subtitle}</p>
          </div>
          <button onClick={onClose} className="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 transition hover:border-[#ff5a1f] hover:text-[#ff5a1f]">
            Close
          </button>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {rows.map((row) => (
            <div key={row.label} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className={`${spaceMono.className} text-[0.62rem] font-semibold tracking-[0.12em] uppercase text-slate-500`}>{row.label}</p>
              <p className={`mt-1 text-sm ${row.highlight ? "font-semibold text-slate-950" : "text-slate-800"}`}>{row.value}</p>
            </div>
          ))}
        </div>

        <div className="mt-5 rounded-xl border border-slate-200 bg-white p-4">
          <p className={`${spaceMono.className} text-[0.62rem] font-semibold tracking-[0.12em] uppercase text-slate-500`}>summary</p>
          <p className="mt-2 text-sm leading-6 text-slate-700">{description}</p>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <a href={ctaLink} target="_blank" rel="noreferrer" className="rounded-full bg-[#ff5a1f] px-5 py-2.5 text-sm font-medium text-white transition hover:bg-[#e94f16]">
            {ctaLabel}
          </a>
          <span className="text-sm text-slate-500">Use this as a starting point for your application.</span>
        </div>
      </div>
    </div>
  )
}

export default function Home() {
  const [page, setPage] = useState<"home" | "internships" | "mentorships">("home")
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
    if (iStipend !== "all" && item.stipendTier !== iStipend) return false
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

  return (
    <div className={`${inter.className} min-h-screen bg-white text-slate-950`}>
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-8">
          <button onClick={() => navigate("home")} className="text-lg font-semibold tracking-tight text-slate-950">
            it girls
          </button>

          <nav className="flex items-center gap-1">
            {(["internships", "mentorships"] as const).map((item) => (
              <button
                key={item}
                onClick={() => navigate(item)}
                className={`${spaceMono.className} rounded-t-xl border border-slate-200 border-b-0 px-5 py-2 text-[0.68rem] font-semibold tracking-[0.12em] uppercase transition ${page === item ? "bg-[#ff5a1f] text-white" : "bg-white text-slate-600 hover:text-[#ff5a1f]"}`}
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
              <h1 className="text-4xl font-semibold tracking-tight text-slate-950 md:text-6xl lg:text-7xl">
                <span className="block">build the career</span>
                <span className="block text-[#ff5a1f]">they said you couldn&apos;t.</span>
              </h1>
              <p className={`${spaceMono.className} mt-5 text-[0.72rem] tracking-[0.15em] uppercase text-slate-500`}>
                curated internships &amp; mentorships for women in tech &amp; beyond
              </p>
              <p className="mt-5 max-w-2xl text-base leading-7 text-slate-600 md:text-lg">
                A cleaner, faster version of the old folder system, rebuilt with the same intent and the full backend-fed dataset.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <a href="#internships" className="rounded-full bg-[#ff5a1f] px-5 py-3 text-sm font-medium text-white transition hover:bg-[#e94f16]">Browse internships</a>
              </div>
            </div>
          </section>

          <section className="border-y border-slate-200 bg-slate-50/70 px-6 py-10 lg:px-8">
            <div className="mx-auto max-w-7xl">
              <p className={`${spaceMono.className} text-[0.68rem] font-semibold tracking-[0.16em] uppercase text-slate-500`}>featured companies</p>
              <div className="mt-5 flex flex-wrap gap-2">
                {companies.map((company) => (
                  <span key={company} className="rounded-full border border-slate-200 bg-white px-3.5 py-2 text-sm text-slate-700 shadow-sm">
                    {company}
                  </span>
                ))}
              </div>
            </div>
          </section>

          <section id="internships" className="mx-auto max-w-7xl px-6 py-16 lg:px-8">
            <SectionHeading kicker="featured" title="Some of the current internships" text={`Loaded from the backend: ${internshipItems.length || 0} internships and ${mentorshipItems.length || 0} mentorships.`} />
            {internshipLoading ? (
              <div className="mt-10 rounded-2xl border border-slate-200 bg-slate-50 py-16 text-center text-sm text-slate-500">Loading internships...</div>
            ) : internshipError ? (
              <div className="mt-10 rounded-2xl border border-red-200 bg-red-50 py-16 text-center text-sm text-red-700">{internshipError}</div>
            ) : (
              <div className="mt-10 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                {featuredInternships.map((intern, index) => (
                  <FolderCard
                    key={intern.id}
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

          <section className="border-y border-slate-200 bg-white px-6 py-10 lg:px-8">
            <div className="mx-auto max-w-7xl">
              <p className={`${spaceMono.className} text-[0.68rem] font-semibold tracking-[0.16em] uppercase text-slate-500`}>what they said</p>
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
                  <div key={item.author} className="rounded-2xl border border-slate-200 bg-slate-50 p-6 shadow-sm">
                    <p className="text-sm leading-7 text-slate-700">&quot;{item.quote}&quot;</p>
                    <p className={`${spaceMono.className} mt-4 text-[0.62rem] font-semibold tracking-[0.12em] uppercase text-[#ff5a1f]`}>{item.author}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <footer className="border-t border-slate-200 px-6 py-8 lg:px-8">
            <div className="mx-auto flex max-w-7xl flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <p className="text-sm text-slate-500">it girls</p>
              <p className={`${spaceMono.className} text-[0.64rem] font-semibold tracking-[0.14em] uppercase text-slate-400`}>internships · mentorships · yc colors</p>
            </div>
          </footer>
        </main>
      )}

      {page === "internships" && (
        <main>
          <section className="mx-auto max-w-7xl px-6 pt-16 lg:px-8 lg:pt-20">
            <div className="max-w-4xl">
              <p className={`${spaceMono.className} text-[0.72rem] font-semibold tracking-[0.18em] uppercase text-[#ff5a1f]`}>internships</p>
              <h1 className="mt-4 text-4xl font-semibold tracking-tight text-slate-950 md:text-5xl">All open roles, cleaned up and easy to scan.</h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">This tab now loads the full internship dataset from the backend, so you get the complete list instead of six samples.</p>
            </div>
          </section>

          <FilterBar stipend={iStipend} setStipend={setIStipend} mode={iMode} setMode={setIMode} cgpa={iCgpa} setCgpa={setICgpa} branch={iBranch} setBranch={setIBranch} branches={internBranches} />

          <section className="mx-auto max-w-7xl px-6 py-10 lg:px-8">
            {internshipLoading ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 py-16 text-center text-sm text-slate-500">Loading internships...</div>
            ) : internshipError ? (
              <div className="rounded-2xl border border-red-200 bg-red-50 py-16 text-center text-sm text-red-700">{internshipError}</div>
            ) : filteredInterns.length === 0 ? (
              <EmptyState clearFn={resetInternFilters} />
            ) : (
              <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                {filteredInterns.map((intern) => (
                  <FolderCard
                    key={intern.id}
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
              <p className={`${spaceMono.className} text-[0.72rem] font-semibold tracking-[0.18em] uppercase text-[#ff5a1f]`}>mentorships</p>
              <h1 className="mt-4 text-4xl font-semibold tracking-tight text-slate-950 md:text-5xl">Guidance with structure.</h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">The mentorship dataset is loaded from the backend as well, so the full list is available and filterable.</p>
            </div>
          </section>

          <FilterBar stipend="all" setStipend={() => {}} mode={mMode} setMode={setMMode} cgpa={mCgpa} setCgpa={setMCgpa} branch={mBranch} setBranch={setMBranch} branches={mentorBranches} hidePay />

          <section className="mx-auto max-w-7xl px-6 py-10 lg:px-8">
            {mentorshipLoading ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 py-16 text-center text-sm text-slate-500">Loading mentorships...</div>
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