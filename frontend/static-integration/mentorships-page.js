import { fetchMentorships } from "./api.js";

const state = {
  page: 1,
  page_size: 12,
  keyword: "",
  source: "",
  company: "",
  gender: "",
  sort_by: "programme_name",
  sort_order: "asc",
};

function el(id) {
  return document.getElementById(id);
}

function card(item) {
  return `
    <article class="mentorship-card">
      <h3>${item.programme_name || "N/A"}</h3>
      <p>${item.company || "N/A"} | ${item.source || "N/A"}</p>
      <p>${item.programme_type || "Mentorship"} | ${item.mode || "Not mentioned"}</p>
      <p>Duration: ${item.duration || "Not mentioned"} | Gender: ${item.gender || "All"}</p>
      <p>${item.description || ""}</p>
      <a href="${item.apply_link || "#"}" target="_blank" rel="noreferrer">Open Programme</a>
    </article>
  `;
}

function renderPagination(meta) {
  const root = el("mentorship-pagination");
  if (!root) return;

  const totalPages = Math.max(1, Math.ceil((meta.total || 0) / (meta.page_size || 1)));
  root.innerHTML = `
    <button id="mentorship-prev" ${meta.page <= 1 ? "disabled" : ""}>Prev</button>
    <span>Page ${meta.page} of ${totalPages}</span>
    <button id="mentorship-next" ${meta.page >= totalPages ? "disabled" : ""}>Next</button>
  `;

  const prev = el("mentorship-prev");
  const next = el("mentorship-next");
  if (prev) {
    prev.onclick = () => {
      if (state.page > 1) {
        state.page -= 1;
        loadMentorships();
      }
    };
  }
  if (next) {
    next.onclick = () => {
      if (state.page < totalPages) {
        state.page += 1;
        loadMentorships();
      }
    };
  }
}

export async function loadMentorships() {
  const list = el("mentorship-list");
  const total = el("mentorship-total");
  const error = el("mentorship-error");

  if (list) list.innerHTML = "Loading mentorship programmes...";
  if (error) error.textContent = "";

  try {
    const payload = await fetchMentorships(state);
    const items = payload.data || [];
    const meta = payload.meta || {};

    if (total) total.textContent = String(meta.total || 0);
    if (list) {
      list.innerHTML = items.length ? items.map(card).join("") : "No mentorship programmes found.";
    }
    renderPagination(meta);
  } catch (err) {
    if (list) list.innerHTML = "";
    if (error) error.textContent = err.message;
  }
}

function wireFilters() {
  const search = el("mentorship-search");
  const source = el("mentorship-source");
  const company = el("mentorship-company");
  const gender = el("mentorship-gender");
  const sortBy = el("mentorship-sort-by");
  const sortOrder = el("mentorship-sort-order");

  if (search) {
    search.addEventListener("input", (e) => {
      state.keyword = e.target.value.trim();
      state.page = 1;
      loadMentorships();
    });
  }
  if (source) {
    source.addEventListener("change", (e) => {
      state.source = e.target.value;
      state.page = 1;
      loadMentorships();
    });
  }
  if (company) {
    company.addEventListener("change", (e) => {
      state.company = e.target.value;
      state.page = 1;
      loadMentorships();
    });
  }
  if (gender) {
    gender.addEventListener("change", (e) => {
      state.gender = e.target.value;
      state.page = 1;
      loadMentorships();
    });
  }
  if (sortBy) {
    sortBy.addEventListener("change", (e) => {
      state.sort_by = e.target.value;
      state.page = 1;
      loadMentorships();
    });
  }
  if (sortOrder) {
    sortOrder.addEventListener("change", (e) => {
      state.sort_order = e.target.value;
      state.page = 1;
      loadMentorships();
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  wireFilters();
  loadMentorships();
});
