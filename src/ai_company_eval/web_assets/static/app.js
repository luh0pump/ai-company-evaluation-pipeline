"use strict";

let currentRun = null;
const byId = (id) => document.getElementById(id);
const runButton = byId("run");
const message = byId("run-message");
const summaryFields = ["companies", "successful", "failed", "average_score", "cache_rate", "runtime_ms"];

function cell(text, className = "") {
  const td = document.createElement("td");
  td.textContent = text;
  td.className = className;
  return td;
}

function closeDetail() {
  byId("detail").hidden = true;
  document.querySelectorAll(".company-button").forEach((button) => button.setAttribute("aria-expanded", "false"));
  document.querySelectorAll("#rows tr").forEach((row) => row.classList.remove("selected"));
}

function showDetail(row, tr, button) {
  closeDetail();
  tr.classList.add("selected");
  button.setAttribute("aria-expanded", "true");
  byId("detail-title").textContent = row.company_name;
  const fields = {
    "Company": row.company_name, "Website": row.website, "Input notes": row.notes,
    "Score": row.score === null ? "Not scored" : `${row.score} / 100`,
    "Recommendation": row.recommendation ?? "Not evaluated",
    "Rationale": row.rationale ?? (row.status === "CACHE_MISS" ? "No evaluation was attempted because cached content is missing." : "No valid evaluation is available."),
    "Processing status": row.status, "Validation status": row.validation_status,
    "Cache status": row.cache_hit ? "Hit — bundled content reused" : "Miss — no content supplied",
  };
  if (row.error) fields["Error detail"] = row.error;
  const list = byId("detail-fields");
  list.replaceChildren();
  for (const [label, value] of Object.entries(fields)) {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = value;
    list.append(dt, dd);
  }
  byId("detail").hidden = false;
  byId("detail").scrollIntoView({block: "nearest"});
}

function render(result) {
  closeDetail();
  for (const field of summaryFields) {
    const value = result.summary[field];
    byId(`kpi-${field}`).textContent = value === null ? "—" : field === "runtime_ms" ? `${value.toFixed(1)} ms` : field === "cache_rate" ? `${value}%` : value;
  }
  const tbody = byId("rows");
  tbody.replaceChildren();
  result.rows.forEach((row) => {
    const tr = document.createElement("tr");
    const name = document.createElement("td");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "company-button";
    button.textContent = row.company_name;
    button.setAttribute("aria-controls", "detail");
    button.setAttribute("aria-expanded", "false");
    button.addEventListener("click", () => showDetail(row, tr, button));
    name.append(button);
    const status = cell("");
    const chip = document.createElement("span");
    chip.className = `chip ${row.status === "SUCCESS" ? "success" : "failure"}`;
    chip.textContent = row.status;
    status.append(chip);
    // Compact label; the full provider recommendation is available in the detail panel and exports.
    const recommendation = row.recommendation === null ? "Not evaluated" : row.recommendation.startsWith("High-priority") ? "Prioritize outreach" : row.recommendation.startsWith("Qualify manually") ? "Qualify manually" : "Low priority";
    tr.append(name, cell(new URL(row.website).hostname, "website"), cell(row.score ?? "—", "score"), cell(recommendation, "recommendation"), status, cell(row.cache_hit ? "Hit" : "Miss", row.cache_hit ? "cache-hit" : "cache-miss"));
    tbody.append(tr);
  });
  byId("empty").hidden = true;
  byId("table-wrap").hidden = false;
  byId("row-count").textContent = `${result.rows.length} of ${result.summary.companies} companies · Synthetic demo data`;
  byId("result-caption").textContent = "company_evaluation / Demo provider / Current run";
  message.textContent = `Run complete · ${result.summary.successful} validated outputs · ${result.summary.failed} isolated ${result.summary.failed === 1 ? "failure" : "failures"} · No external calls`;
  ["export-csv", "export-json", "reset"].forEach((id) => byId(id).disabled = false);
}

runButton.addEventListener("click", async () => {
  runButton.disabled = true;
  runButton.textContent = "Evaluating…";
  byId("reset").disabled = true;
  byId("export-csv").disabled = true;
  byId("export-json").disabled = true;
  message.classList.remove("error");
  message.textContent = "Evaluating bundled content and validating each result…";
  try {
    const response = await fetch("/api/demo/run", {method: "POST", signal: AbortSignal.timeout(15000)});
    if (!response.ok) throw new Error("Run failed");
    const result = await response.json();
    render(result);
    currentRun = result;
  } catch {
    message.textContent = currentRun ? "The run could not complete. Previous results are still shown. Try again." : "The run could not complete. Please try again.";
    message.classList.add("error");
    ["export-csv", "export-json", "reset"].forEach((id) => byId(id).disabled = !currentRun);
  } finally {
    runButton.disabled = false;
    runButton.textContent = "Run Evaluation →";
  }
});

function download(format) {
  if (!currentRun) return;
  const mime = format === "csv" ? "text/csv;charset=utf-8" : "application/json;charset=utf-8";
  const blob = new Blob([currentRun.exports[format]], {type: mime});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `company_evaluation_results.${format}`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

byId("export-csv").addEventListener("click", () => download("csv"));
byId("export-json").addEventListener("click", () => download("json"));
byId("close-detail").addEventListener("click", () => {
  const selected = document.querySelector('.company-button[aria-expanded="true"]');
  closeDetail();
  selected?.focus();
});
byId("reset").addEventListener("click", () => {
  currentRun = null;
  closeDetail();
  byId("rows").replaceChildren();
  byId("detail-fields").replaceChildren();
  byId("empty").hidden = false;
  byId("table-wrap").hidden = true;
  summaryFields.forEach((field) => byId(`kpi-${field}`).textContent = "—");
  ["export-csv", "export-json", "reset"].forEach((id) => byId(id).disabled = true);
  byId("row-count").textContent = "No results yet";
  byId("result-caption").textContent = "Ready to evaluate the synthetic dataset.";
  message.classList.remove("error");
  message.textContent = "Run the pipeline to inspect scores, validation and per-row outcomes.";
  runButton.focus();
});
