export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:5000"

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
  const response = await fetch(buildUrl(path, params), {
    signal,
    cache: "no-store",
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed with status ${response.status}`)
  }

  return (await response.json()) as T
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
