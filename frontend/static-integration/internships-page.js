import { fetchInternships } from "./api.js";

const state = {
  page: 1,
  page_size: 12,
  keyword: "",
  source: "",
  gender: "",
  sort_by: "title",
  sort_order: "asc",
};

function el(id) {
  return document.getElementById(id);
}

function card(item) {
  return `
    <article class="internship-card">
      <h3>${item.title || "N/A"}</h3>
      <p>${item.company || "N/A"} | ${item.source || "N/A"}</p>
      <p>${item.location || "N/A"}</p>
      <p>CGPA: ${item.cgpa_required || "Not mentioned"} | Gender: ${item.gender || "All"}</p>
      <a href="${item.apply_link || "#"}" target="_blank" rel="noreferrer">Apply</a>
    </article>
  `;
}

function renderPagination(meta) {
  const root = el("internship-pagination");
  if (!root) return;

  const totalPages = Math.max(1, Math.ceil((meta.total || 0) / (meta.page_size || 1)));
  root.innerHTML = `
    <button id="internship-prev" ${meta.page <= 1 ? "disabled" : ""}>Prev</button>
    <span>Page ${meta.page} of ${totalPages}</span>
    <button id="internship-next" ${meta.page >= totalPages ? "disabled" : ""}>Next</button>
  `;

  const prev = el("internship-prev");
  const next = el("internship-next");
  if (prev) {
    prev.onclick = () => {
      if (state.page > 1) {
        state.page -= 1;
        loadInternships();
      }
    };
  }
  if (next) {
    next.onclick = () => {
      if (state.page < totalPages) {
        state.page += 1;
        loadInternships();
      }
    };
  }
}

export async function loadInternships() {
  const list = el("internship-list");
  const total = el("internship-total");
  const error = el("internship-error");

  if (list) list.innerHTML = "Loading internships...";
  if (error) error.textContent = "";

  try {
    const payload = await fetchInternships(state);
    const items = payload.data || [];
    const meta = payload.meta || {};

    if (total) total.textContent = String(meta.total || 0);
    if (list) {
      list.innerHTML = items.length ? items.map(card).join("") : "No internships found.";
    }
    renderPagination(meta);
  } catch (err) {
    if (list) list.innerHTML = "";
    if (error) error.textContent = err.message;
  }
}

function wireFilters() {
  const search = el("internship-search");
  const source = el("internship-source");
  const gender = el("internship-gender");
  const sortBy = el("internship-sort-by");
  const sortOrder = el("internship-sort-order");

  if (search) {
    search.addEventListener("input", (e) => {
      state.keyword = e.target.value.trim();
      state.page = 1;
      loadInternships();
    });
  }
  if (source) {
    source.addEventListener("change", (e) => {
      state.source = e.target.value;
      state.page = 1;
      loadInternships();
    });
  }
  if (gender) {
    gender.addEventListener("change", (e) => {
      state.gender = e.target.value;
      state.page = 1;
      loadInternships();
    });
  }
  if (sortBy) {
    sortBy.addEventListener("change", (e) => {
      state.sort_by = e.target.value;
      state.page = 1;
      loadInternships();
    });
  }
  if (sortOrder) {
    sortOrder.addEventListener("change", (e) => {
      state.sort_order = e.target.value;
      state.page = 1;
      loadInternships();
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  wireFilters();
  loadInternships();
});
