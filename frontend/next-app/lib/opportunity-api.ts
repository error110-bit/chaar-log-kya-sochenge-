export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:5000"

const STATIC_DATA_BASE_URL = "https://raw.githubusercontent.com/error110-bit/chaar-log-kya-sochenge-/main"

export type ListResponse<T> = {
  meta: {
    total: number
    page: number
    page_size: number
    sort_by: string
    sort_order: string
    scraped_at: string | null
  }
  data: T[]
}

export type InternshipItem = {
  source: string
  title: string
  company: string
  location: string
  stipend: string
  duration: string
  mode: string
  internship_type: string
  branch_required: string
  cgpa_required: string
  gender: string
  eligibility_raw: string
  skills: string
  deadline: string
  applicants: string
  apply_link: string
}

export type MentorshipItem = {
  source: string
  company: string
  programme_name: string
  programme_type: string
  description: string
  duration: string
  mode: string
  eligibility: string
  branch_required: string
  cgpa_required: string
  gender: string
  stipend_or_benefits: string
  deadline: string
  apply_link: string
  how_to_apply: string
}

type QueryValue = string | number | undefined | null

type StaticDataset<T> = {
  scraped_at?: string | null
  total?: number
  internships?: T[]
  mentorship_programmes?: T[]
}

type StaticDatasetKind = "internships" | "mentorships"

const staticDatasetCache = new Map<StaticDatasetKind, Promise<unknown>>()

function getStaticDatasetUrl(kind: StaticDatasetKind) {
  return kind === "internships"
    ? `${STATIC_DATA_BASE_URL}/internships_latest.json`
    : `${STATIC_DATA_BASE_URL}/mentorship_latest.json`
}

function getStaticDatasetItems<T>(dataset: StaticDataset<T>, kind: StaticDatasetKind) {
  return kind === "internships" ? dataset.internships ?? [] : dataset.mentorship_programmes ?? []
}

function loadStaticDataset<T>(kind: StaticDatasetKind) {
  const cached = staticDatasetCache.get(kind)
  if (cached) return cached as Promise<StaticDataset<T>>

  const request = fetch(getStaticDatasetUrl(kind), { cache: "force-cache" })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Static dataset request failed with status ${response.status}`)
      }
      return (await response.json()) as StaticDataset<T>
    })

  staticDatasetCache.set(kind, request)
  return request
}

async function fallbackListResponse<T>(kind: StaticDatasetKind, params?: Record<string, QueryValue>) {
  const dataset = await loadStaticDataset<T>(kind)
  const items = getStaticDatasetItems(dataset, kind)
  return {
    meta: {
      total: items.length,
      page: Number(params?.page ?? 1),
      page_size: items.length || 1,
      sort_by: String(params?.sort_by ?? "title"),
      sort_order: String(params?.sort_order ?? "asc"),
      scraped_at: dataset.scraped_at ?? null,
    },
    data: items,
  }
}

function buildUrl(path: string, params?: Record<string, QueryValue>) {
  const url = new URL(path, API_BASE_URL)

  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null || value === "") continue
      url.searchParams.set(key, String(value))
    }
  }

  return url.toString()
}

async function requestJson<T>(path: string, params?: Record<string, QueryValue>, signal?: AbortSignal) {
  try {
    const response = await fetch(buildUrl(path, params), {
      signal,
      cache: "no-store",
    })

    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || `Request failed with status ${response.status}`)
    }

    return (await response.json()) as T
  } catch (error) {
    if (path === "/internships") {
      return (await fallbackListResponse<InternshipItem>("internships", params)) as T
    }

    if (path === "/mentorships") {
      return (await fallbackListResponse<MentorshipItem>("mentorships", params)) as T
    }

    throw error
  }
}

export function fetchInternships(
  params?: {
    keyword?: string
    source?: string
    company?: string
    mode?: string
    internship_type?: string
    branch?: string
    max_cgpa?: string
    sort_by?: string
    sort_order?: string
    page?: number
    page_size?: number
  },
  signal?: AbortSignal,
) {
  return requestJson<ListResponse<InternshipItem>>("/internships", params, signal)
}

export function fetchMentorships(
  params?: {
    keyword?: string
    source?: string
    company?: string
    mode?: string
    programme_type?: string
    branch?: string
    max_cgpa?: string
    sort_by?: string
    sort_order?: string
    page?: number
    page_size?: number
  },
  signal?: AbortSignal,
) {
  return requestJson<ListResponse<MentorshipItem>>("/mentorships", params, signal)
}
