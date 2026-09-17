// LocalLLM Feed クライアント（動的スコアリング・検索・エクスポート）。
// スコア配点/オフロード算出は LLF-SC-001 準拠。scoring.json が無い場合は既定値を使う。

const STORAGE_KEY = "llf_prefs";

// scoring.json 取得失敗時のフォールバック既定値（LLF-SC-001 §2）
const DEFAULT_SCORING = {
  vram_match: {
    param_tiers: [3, 8, 14, 24, 35],
    gb8: { scores: [8, 10, 4, -6, -12] },
    gb12: { scores: [4, 10, 10, -2, -8] },
    gb16: { scores: [2, 8, 10, 6, -4] },
    gb24: { scores: [0, 4, 8, 10, 6] },
    gb32: { scores: [0, 2, 6, 10, 10] },
  },
  quantization: {
    sweet_spot: ["Q4_K_M", "Q5_K_M"],
    sweet_spot_bonus: 6.0,
    high_fidelity: ["Q8_0", "Q6_K"],
    high_fidelity_bonus: 5.0,
    high_fidelity_min_vram_gb: 32,
  },
  efficiency: { distilled_speed_bonus: 5.0 },
  offload: {
    safety_margin: 0.9,
    os_reserved_gb: 1.0,
    kv_cache_gb: 1.5,
    bytes_per_param_q4: 0.5,
    default_layers_35b: 40,
  },
};

// カード上で強調表示する代表量子化フォーマット
const HIGHLIGHT_QUANTS = ["Q4_K_M", "Q5_K_M", "Q8_0", "Q6_K"];

let allModels = [];
let scoring = DEFAULT_SCORING;
let miniSearch = null;

const el = (id) => document.getElementById(id);

function loadPrefs() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}
function savePrefs(prefs) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
}

// --- スコアリング（LLF-SC-001 §3） ---
function paramTierIndex(paramsB, tiers) {
  for (let i = 0; i < tiers.length; i++) {
    if (paramsB <= tiers[i]) return i;
  }
  return tiers.length - 1; // 最大帯を超える場合は最終列
}

function vramKey(vramGb) {
  if (vramGb <= 8) return "gb8";
  if (vramGb <= 12) return "gb12";
  if (vramGb <= 16) return "gb16";
  if (vramGb <= 24) return "gb24";
  return "gb32";
}

function scoreModel(model, vramGb, priority) {
  const vm = scoring.vram_match;
  const tiers = vm.param_tiers;
  const idx = paramTierIndex(model.params_b, tiers);
  const row = vm[vramKey(vramGb)] || { scores: [] };
  let total = (row.scores && row.scores[idx]) || 0;

  const q = scoring.quantization;
  const quants = model.quants || [];
  if (q.sweet_spot.some((s) => quants.includes(s))) total += q.sweet_spot_bonus;
  if (vramGb >= q.high_fidelity_min_vram_gb && q.high_fidelity.some((s) => quants.includes(s))) {
    total += q.high_fidelity_bonus;
  }

  if (model.is_distilled && priority === "speed") {
    total += scoring.efficiency.distilled_speed_bonus;
  }
  return Math.max(0, total);
}

// --- オフロード算出（LLF-SC-001 §4） ---
function estimateGpuLayers(model, vramGb) {
  const o = scoring.offload;
  const modelSize = model.params_b * o.bytes_per_param_q4;
  const usable = (vramGb - o.os_reserved_gb - o.kv_cache_gb) * o.safety_margin;
  const totalLayers = Math.max(1, Math.round((model.params_b / 35) * o.default_layers_35b) || o.default_layers_35b);
  const gbPerLayer = modelSize / totalLayers;
  if (gbPerLayer <= 0) return 0;
  let layers = Math.floor(usable / gbPerLayer);
  if (layers < 0) layers = 0;
  if (layers > totalLayers) layers = totalLayers;
  return layers;
}

// --- エクスポート（LLF-DD-001 §5） ---
const TEMPLATE_RULES = [
  { re: /llama-?3/i, tpl: "Llama3" },
  { re: /qwen/i, tpl: "ChatML" },
  { re: /command-?r/i, tpl: "ChatML" },
  { re: /mi(s|x)tral/i, tpl: "Mistral" },
];
function detectTemplate(base) {
  for (const r of TEMPLATE_RULES) if (r.re.test(base || "")) return r.tpl;
  return "汎用";
}

function bashExport(model, vramGb) {
  const quant = (model.quants && model.quants[0]) || "Q4_K_M";
  const layers = estimateGpuLayers(model, vramGb);
  return [
    `# ${model.id}`,
    `export MODEL_REPO="${model.id}"`,
    `export QUANT="${quant}"`,
    `export N_GPU_LAYERS=${layers}`,
    `huggingface-cli download "${model.id}" --include "*${quant}*.gguf" --local-dir ./models`,
  ].join("\n");
}

function modelfileExport(model) {
  const quant = (model.quants && model.quants[0]) || "Q4_K_M";
  const tpl = detectTemplate(model.base);
  return [
    `# Ollama Modelfile for ${model.id} (${tpl} template)`,
    `FROM ./models/${model.base}-${quant}.gguf`,
    `PARAMETER temperature 0.7`,
  ].join("\n");
}

function copyText(text, message) {
  navigator.clipboard.writeText(text).then(() => showToast(message));
}
window.copyBash = (id) => {
  const m = allModels.find((x) => x.id === id);
  if (m) copyText(bashExport(m, currentVram()), "Bash設定をコピーしました");
};
window.copyModelfile = (id) => {
  const m = allModels.find((x) => x.id === id);
  if (m) copyText(modelfileExport(m), "Modelfileをコピーしました");
};

// --- 描画 ---
function currentVram() {
  return parseInt(el("vramSelect").value, 10);
}

function getVisibleModels() {
  const query = el("searchInput").value.trim();
  const vram = currentVram();
  const priority = el("prioritySelect").value;
  const distilledOnly = el("distilledOnly").checked;

  let list = allModels;
  if (query && miniSearch) {
    const ids = new Set(miniSearch.search(query).map((r) => r.id));
    list = list.filter((m) => ids.has(m.id));
  }
  if (distilledOnly) list = list.filter((m) => m.is_distilled);

  return list
    .map((m) => ({ model: m, score: scoreModel(m, vram, priority) }))
    .sort((a, b) => b.score - a.score);
}

function render() {
  const scored = getVisibleModels();
  const vram = currentVram();
  el("shownCount").textContent = scored.length;

  const listEl = el("modelList");
  listEl.innerHTML = "";
  if (scored.length === 0) {
    el("emptyState").classList.remove("hidden");
    return;
  }
  el("emptyState").classList.add("hidden");

  for (const { model, score } of scored) {
    const layers = estimateGpuLayers(model, vram);
    const quants = model.quants || [];
    const primary = quants.filter((q) => HIGHLIGHT_QUANTS.includes(q));
    const shown = primary.length ? primary : quants.slice(0, 3);
    const remain = quants.length - shown.length;
    const quantBadges =
      shown
        .map((q) => `<span class="text-xs text-emerald-300 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">${q}</span>`)
        .join(" ") +
      (remain > 0
        ? ` <span class="text-xs text-slate-400 bg-slate-900/60 px-2 py-0.5 rounded border border-slate-800">+${remain}</span>`
        : "");
    const distill = model.is_distilled
      ? '<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">蒸留</span>'
      : "";
    const card = document.createElement("div");
    card.className = "bg-slate-800/80 border border-slate-700/80 p-5 rounded-2xl space-y-3";
    card.innerHTML = `
      <div class="flex items-start justify-between gap-4">
        <div>
          <div class="flex items-center space-x-2 flex-wrap gap-y-1">
            <a href="https://huggingface.co/${model.id}" target="_blank" rel="noopener noreferrer"
               class="text-base font-bold text-emerald-300 hover:underline">${model.id}</a>
            <span class="px-2 py-0.5 rounded-full text-xs bg-slate-700 text-slate-300">${model.params_b}B</span>
            ${distill}
          </div>
          <p class="text-xs text-slate-300 mt-1.5 leading-relaxed">${escapeHtml(model.tldr || "説明文なし")}</p>
          <div class="flex items-center gap-3 mt-1.5 text-xs text-slate-500">
            <span>⬇ ${(model.downloads || 0).toLocaleString()}</span>
            <span>📅 ${model.date || "-"}</span>
            <span>👤 ${escapeHtml(model.author || "")}</span>
          </div>
        </div>
        <div class="text-right flex-shrink-0">
          <div class="text-xs text-slate-400">Score</div>
          <div class="text-xl font-black bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">${score.toFixed(1)}</div>
        </div>
      </div>
      <div class="flex flex-wrap gap-2 items-center pt-2 border-t border-slate-700/40">
        ${quantBadges}
      </div>
      <div class="flex items-center justify-between text-xs text-slate-400">
        <span>推奨 n_gpu_layers: <span class="text-slate-200 font-semibold">${layers}</span> (VRAM ${vram}GB)</span>
        <div class="space-x-2">
          <button onclick="copyBash('${model.id}')" class="px-2.5 py-1 rounded bg-slate-700/60 hover:bg-slate-700">Bash</button>
          <button onclick="copyModelfile('${model.id}')" class="px-2.5 py-1 rounded bg-slate-700/60 hover:bg-slate-700">Modelfile</button>
        </div>
      </div>`;
    listEl.appendChild(card);
  }
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function showToast(msg) {
  el("toastMsg").textContent = msg;
  const t = el("toast");
  t.classList.remove("translate-y-20", "opacity-0");
  setTimeout(() => t.classList.add("translate-y-20", "opacity-0"), 2200);
}

function setupSearch() {
  miniSearch = new MiniSearch({
    fields: ["id", "base", "tldr", "quants_str"],
    storeFields: ["id"],
    searchOptions: { fuzzy: 0.2, prefix: true },
  });
  miniSearch.addAll(
    allModels.map((m) => ({ ...m, quants_str: (m.quants || []).join(" ") }))
  );
}

async function init() {
  const prefs = loadPrefs();
  if (prefs.vram) el("vramSelect").value = prefs.vram;
  if (prefs.priority) el("prioritySelect").value = prefs.priority;
  if (prefs.distilledOnly) el("distilledOnly").checked = true;

  try {
    const res = await fetch("./data/scoring.json");
    if (res.ok) scoring = await res.json();
  } catch { /* 既定値を使用 */ }

  try {
    const res = await fetch("./data/models_feed.json");
    if (!res.ok) throw new Error("feed fetch failed");
    const feed = await res.json();
    if (feed.schema_version !== 1) {
      showToast("フィードのスキーマ版が未対応です");
    }
    allModels = feed.models || [];
    el("generatedAt").textContent = (feed.generated_at || "").slice(0, 10) || "-";
  } catch {
    allModels = [];
  }

  el("totalCount").textContent = allModels.length;
  setupSearch();
  render();
}

function onChange() {
  savePrefs({
    vram: el("vramSelect").value,
    priority: el("prioritySelect").value,
    distilledOnly: el("distilledOnly").checked,
  });
  render();
}

el("searchInput").addEventListener("input", render);
el("vramSelect").addEventListener("change", onChange);
el("prioritySelect").addEventListener("change", onChange);
el("distilledOnly").addEventListener("change", onChange);

init();