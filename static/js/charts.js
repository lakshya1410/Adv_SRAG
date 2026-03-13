/**
 * charts.js — Chart.js visualizations for the Self-RAG landing page
 * Renders the performance comparison bar chart and quality radar chart.
 */

"use strict";

// Palette (matches CSS variables)
const ACCENT    = "#ff3417";
const ACCENT_SOFT = "#f1a377";
const INK       = "#15151a";
const MUTED     = "#585864";
const LINE      = "#d4ceca";
const SURFACE   = "#f5f0ee";

const CHART_FONT = "'IBM Plex Mono', monospace";

Chart.defaults.font.family = CHART_FONT;
Chart.defaults.color       = MUTED;

let comparisonChart = null;
let radarChart = null;
const CHARTS_INIT_KEY = "__selfRagChartsInitDone";

function buildComparisonChart(ctx) {
  // Destroy existing chart on the same canvas to avoid duplicate render loops.
  const existing = Chart.getChart(ctx);
  if (existing) existing.destroy();

  return new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Answer Accuracy", "Context Relevance", "Hallucination\nReduction", "Reliability"],
      datasets: [
        {
          label: "Traditional RAG",
          data: [68, 72, 45, 62],
          backgroundColor: "rgba(88,88,100,0.25)",
          borderColor: MUTED,
          borderWidth: 1.5,
          borderRadius: 6,
        },
        {
          label: "Self-RAG",
          data: [91, 94, 88, 93],
          backgroundColor: "rgba(255,52,23,0.2)",
          borderColor: ACCENT,
          borderWidth: 1.5,
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      resizeDelay: 220,
      scales: {
        x: {
          grid: { color: LINE },
          ticks: { font: { size: 11 } },
        },
        y: {
          min: 0,
          max: 100,
          grid: { color: LINE },
          ticks: {
            font: { size: 11 },
            callback: (v) => v + "%",
          },
        },
      },
      plugins: {
        legend: {
          position: "top",
          labels: {
            boxWidth: 12,
            padding: 16,
            font: { size: 11 },
          },
        },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y}%`,
          },
        },
      },
      animation: {
        duration: 900,
        easing: "easeOutQuart",
      },
      transitions: {
        resize: {
          animation: {
            duration: 0,
          },
        },
      },
    },
  });
}

function buildRadarChart(ctx) {
  const existing = Chart.getChart(ctx);
  if (existing) existing.destroy();

  return new Chart(ctx, {
    type: "radar",
    data: {
      labels: [
        "Answer Accuracy",
        "Context Relevance",
        "Hallucination Reduction",
        "Reliability",
        "Query Rewriting",
        "Self-Grounding",
      ],
      datasets: [
        {
          label: "Traditional RAG",
          data: [68, 72, 45, 62, 30, 10],
          backgroundColor: "rgba(88,88,100,0.12)",
          borderColor: MUTED,
          borderWidth: 1.5,
          pointBackgroundColor: MUTED,
          pointRadius: 3,
        },
        {
          label: "Self-RAG",
          data: [91, 94, 88, 93, 87, 95],
          backgroundColor: "rgba(255,52,23,0.1)",
          borderColor: ACCENT,
          borderWidth: 2,
          pointBackgroundColor: ACCENT,
          pointRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      resizeDelay: 220,
      scales: {
        r: {
          min: 0,
          max: 100,
          beginAtZero: true,
          grid: { color: LINE },
          angleLines: { color: LINE },
          pointLabels: {
            font: { size: 11 },
            color: MUTED,
          },
          ticks: {
            font: { size: 10 },
            stepSize: 25,
            callback: (v) => v + "%",
          },
        },
      },
      plugins: {
        legend: {
          position: "top",
          labels: {
            boxWidth: 12,
            padding: 16,
            font: { size: 11 },
          },
        },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.r}%`,
          },
        },
      },
      animation: {
        duration: 1000,
        easing: "easeOutQuart",
      },
      transitions: {
        resize: {
          animation: {
            duration: 0,
          },
        },
      },
    },
  });
}

function initCharts() {
  if (window[CHARTS_INIT_KEY]) return;
  window[CHARTS_INIT_KEY] = true;

  const compCtx = document.getElementById("comparisonChart");
  const radarCtx = document.getElementById("radarChart");

  if (compCtx) comparisonChart = buildComparisonChart(compCtx);
  if (radarCtx) radarChart = buildRadarChart(radarCtx);
}

// Initialise charts once per page load.
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initCharts, { once: true });
} else {
  initCharts();
}
