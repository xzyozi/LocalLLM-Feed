// ScholarRepo-Finder クライアントサイド検索 & UI ロジック (i18n 多言語対応)

let currentLang = localStorage.getItem("srf_lang") || "ja";
let allRepos = [];
let miniSearch = null;

// i18n 翻訳辞書
const I18N = {
  ja: {
    langLabel: "English",
    pageTitle: "ScholarRepo-Finder 🔍📚 | 学術研究・アルゴリズム検証用OSS特化型検索",
    subtitle: "学術研究・アルゴリズム検証用OSS特化型 探索エンジン",
    exportBtn: "📥 Markdown一括保存",
    searchLabel: "キーワード検索",
    searchPlaceholder: "例: routing, simpy, vrp...",
    filterTitle: "絞り込みフィルター",
    reset: "リセット",
    lang: "主要言語",
    allLang: "すべての言語",
    minScore: "最低総合スコア",
    scoreUnit: "点",
    paperCheck: "📄 論文リンク (DOI / arXiv) 必須",
    eduCheck: "🎓 研究・教育機関 (.edu/.ac) のみ",
    totalRepo: "登録OSS総数:",
    displaying: "表示中:",
    resultsPrefix: "検索結果:",
    resultsSuffix: "件の優良学術OSS",
    sortBy: "並び替え:",
    sortScore: "総合スコア順 (高→低)",
    sortStars: "スター数順",
    sortUpdated: "最終更新日順",
    emptyTitle: "該当するリポジトリが見つかりませんでした",
    emptySubtitle: "検索条件や最低スコアを緩めてお試しください。",
    totalScoreBadge: "総合スコア",
    paperBadge: "📄 論文/DOI",
    pwcOfficialBadge: "🔗 PWC公式一致",
    eduBadge: "🎓 学術機関",
    copyMdBtn: "📋 Copy MD",
    copySuccess: "Markdown引用をコピーしました",
    noExportData: "エクスポート対象のリポジトリがありません",
    downloadSuccess: "Markdown ファイルをダウンロードしました！",
    unitCount: "件",
    updatedPrefix: "最終更新:"
  },
  en: {
    langLabel: "日本語",
    pageTitle: "ScholarRepo-Finder 🔍📚 | Academic Research & Algorithm Verification OSS",
    subtitle: "Discovery Engine for Academic Research & Algorithm Verification OSS",
    exportBtn: "📥 Export to Markdown",
    searchLabel: "Keyword Search",
    searchPlaceholder: "e.g., routing, simpy, vrp...",
    filterTitle: "Filters",
    reset: "Reset",
    lang: "Primary Language",
    allLang: "All Languages",
    minScore: "Minimum Score",
    scoreUnit: "pts",
    paperCheck: "📄 Paper Link (DOI / arXiv) Required",
    eduCheck: "🎓 Academic Institution (.edu/.ac) Only",
    totalRepo: "Total OSS:",
    displaying: "Showing:",
    resultsPrefix: "Results:",
    resultsSuffix: "curated academic OSS found",
    sortBy: "Sort by:",
    sortScore: "Total Score (High → Low)",
    sortStars: "Stars",
    sortUpdated: "Recently Updated",
    emptyTitle: "No matching repositories found",
    emptySubtitle: "Try adjusting your search query or lowering the score threshold.",
    totalScoreBadge: "Total Score",
    paperBadge: "📄 Paper/DOI",
    pwcOfficialBadge: "🔗 PWC Official Match",
    eduBadge: "🎓 Academic",
    copyMdBtn: "📋 Copy MD",
    copySuccess: "Copied Markdown citation to clipboard",
    noExportData: "No repositories available to export",
    downloadSuccess: "Downloaded Markdown summary file!",
    unitCount: "items",
    updatedPrefix: "Updated:"
  }
};

// DOM Elements
const searchInput = document.getElementById("searchInput");
const langSelect = document.getElementById("langSelect");
const scoreRange = document.getElementById("scoreRange");
const scoreVal = document.getElementById("scoreVal");
const paperCheck = document.getElementById("paperCheck");
const eduCheck = document.getElementById("eduCheck");
const sortSelect = document.getElementById("sortSelect");
const resetFiltersBtn = document.getElementById("resetFiltersBtn");
const exportMdBtn = document.getElementById("exportMdBtn");
const langToggleBtn = document.getElementById("langToggleBtn");
const langLabel = document.getElementById("langLabel");

const repoList = document.getElementById("repoList");
const emptyState = document.getElementById("emptyState");
const totalRepoCount = document.getElementById("totalRepoCount");
const filteredRepoCount = document.getElementById("filteredRepoCount");
const resultCountLabel = document.getElementById("resultCountLabel");
const toast = document.getElementById("toast");
const toastMsg = document.getElementById("toastMsg");

// 1. 初期化
async function initApp() {
  applyI18n();

  try {
    const res = await fetch("./data/repos.json");
    if (!res.ok) throw new Error("Failed to load repos.json");
    allRepos = await res.json();
  } catch (e) {
    console.warn("Using sample fallback data:", e);
    allRepos = getSampleFallbackData();
  }

  setupMiniSearch();
  populateLanguageFilter();
  renderResults();

  const t = I18N[currentLang];
  totalRepoCount.textContent = `${allRepos.length} ${t.unitCount}`;
}

// 2. i18n 文言適用
function applyI18n() {
  const t = I18N[currentLang];
  document.documentElement.lang = currentLang;
  document.title = t.pageTitle;
  langLabel.textContent = t.langLabel;

  document.getElementById("headerSubtitle").textContent = t.subtitle;
  document.getElementById("exportMdBtnText").textContent = t.exportBtn;
  document.getElementById("lblSearch").textContent = t.searchLabel;
  searchInput.placeholder = t.searchPlaceholder;
  document.getElementById("lblFilterTitle").textContent = t.filterTitle;
  resetFiltersBtn.textContent = t.reset;
  document.getElementById("lblLang").textContent = t.lang;
  document.getElementById("optAllLang").textContent = t.allLang;
  document.getElementById("lblMinScore").textContent = t.minScore;
  scoreVal.textContent = `${scoreRange.value}.0 ${t.scoreUnit}`;
  document.getElementById("lblPaperCheck").textContent = t.paperCheck;
  document.getElementById("lblEduCheck").textContent = t.eduCheck;
  document.getElementById("lblTotalRepo").textContent = t.totalRepo;
  document.getElementById("lblDisplaying").textContent = t.displaying;
  document.getElementById("lblResultsPrefix").textContent = t.resultsPrefix;
  document.getElementById("lblResultsSuffix").textContent = t.resultsSuffix;
  document.getElementById("lblSortBy").textContent = t.sortBy;
  document.getElementById("optSortScore").textContent = t.sortScore;
  document.getElementById("optSortStars").textContent = t.sortStars;
  document.getElementById("optSortUpdated").textContent = t.sortUpdated;
  document.getElementById("lblEmptyTitle").textContent = t.emptyTitle;
  document.getElementById("lblEmptySubtitle").textContent = t.emptySubtitle;
}

// 3. MiniSearch インデックス構築
function setupMiniSearch() {
  miniSearch = new MiniSearch({
    fields: ["id", "name", "desc", "lang", "topics", "libs"],
    storeFields: ["id"],
    searchOptions: {
      boost: { name: 2, topics: 1.5, id: 1.2 },
      fuzzy: 0.2,
      prefix: true
    }
  });
  miniSearch.addAll(allRepos);
}

// 4. 言語フィルター一覧の生成
function populateLanguageFilter() {
  const languages = [...new Set(allRepos.map(r => r.lang).filter(Boolean))].sort();
  languages.forEach(lang => {
    const opt = document.createElement("option");
    opt.value = lang;
    opt.textContent = lang;
    langSelect.appendChild(opt);
  });
}

// 5. 検索＆フィルタリング実行
function getFilteredRepos() {
  const query = searchInput.value.trim();
  const selectedLang = langSelect.value;
  const minScore = parseFloat(scoreRange.value);
  const requirePaper = paperCheck.checked;
  const requireEdu = eduCheck.checked;
  const sortBy = sortSelect.value;

  let results = allRepos;

  if (query && miniSearch) {
    const matchedIds = new Set(miniSearch.search(query).map(res => res.id));
    results = results.filter(r => matchedIds.has(r.id));
  }

  results = results.filter(r => {
    if (selectedLang && r.lang !== selectedLang) return false;
    if (r.score < minScore) return false;
    if (requirePaper && !r.paper) return false;
    if (requireEdu && !r.edu) return false;
    return true;
  });

  results.sort((a, b) => {
    if (sortBy === "score_desc") return b.score - a.score;
    if (sortBy === "stars_desc") return b.stars - a.stars;
    if (sortBy === "updated_desc") return new Date(b.updated) - new Date(a.updated);
    return 0;
  });

  return results;
}

// 6. 描画処理
function renderResults() {
  const t = I18N[currentLang];
  const repos = getFilteredRepos();
  filteredRepoCount.textContent = `${repos.length} ${t.unitCount}`;
  resultCountLabel.textContent = repos.length;

  repoList.innerHTML = "";

  if (repos.length === 0) {
    emptyState.classList.remove("hidden");
    return;
  }
  emptyState.classList.add("hidden");

  repos.forEach(repo => {
    const card = document.createElement("div");
    card.className = "bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 hover:border-indigo-500/50 p-5 rounded-2xl transition duration-200 shadow-sm flex flex-col space-y-3";

    const paperBadge = repo.paper ? `<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">${t.paperBadge}</span>` : '';
    const pwcBadge = repo.pwc_status === "matched_official" ? `<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-violet-500/10 text-violet-300 border border-violet-500/20">${t.pwcOfficialBadge}</span>` : '';
    const eduBadge = repo.edu ? `<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">${t.eduBadge}</span>` : '';
    const langBadge = `<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-700 text-slate-300">${repo.lang}</span>`;
    const topicTags = (repo.topics || []).slice(0, 5).map(tag => `<span class="text-xs text-slate-400 bg-slate-900/60 px-2 py-0.5 rounded border border-slate-800">#${tag}</span>`).join(" ");

    card.innerHTML = `
      <div class="flex items-start justify-between gap-4">
        <div>
          <div class="flex items-center space-x-2 flex-wrap gap-y-1">
            <a href="${repo.url}" target="_blank" rel="noopener noreferrer" class="text-base font-bold text-indigo-300 hover:text-indigo-200 hover:underline">
              ${repo.id}
            </a>
            ${langBadge}
            ${paperBadge}
            ${pwcBadge}
            ${eduBadge}
          </div>
          <p class="text-xs text-slate-400 mt-1.5 leading-relaxed">${repo.desc || ""}</p>
        </div>
        <div class="text-right flex-shrink-0">
          <div class="text-xs text-slate-400">${t.totalScoreBadge}</div>
          <div class="text-xl font-black bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">${repo.score.toFixed(1)}</div>
        </div>
      </div>

      <div class="flex items-center justify-between pt-2 border-t border-slate-700/40 text-xs text-slate-400 flex-wrap gap-2">
        <div class="flex items-center space-x-4">
          <span>⭐ ${repo.stars} stars</span>
          <span>📅 ${t.updatedPrefix} ${repo.updated}</span>
          ${repo.libs && repo.libs.length ? `<span>🧪 ${repo.libs.join(", ")}</span>` : ""}
        </div>
        <div class="flex items-center space-x-2">
          ${topicTags}
          <button onclick="copyItemMarkdown('${repo.id}')" class="ml-2 px-2.5 py-1 rounded bg-slate-700/60 hover:bg-slate-700 text-slate-300 hover:text-white transition" title="Copy Markdown citation">
            ${t.copyMdBtn}
          </button>
        </div>
      </div>
    `;

    repoList.appendChild(card);
  });
}

// 7. Markdown 一括ダウンロード
function exportToMarkdown() {
  const t = I18N[currentLang];
  const repos = getFilteredRepos();
  if (repos.length === 0) {
    showToast(t.noExportData);
    return;
  }

  const query = searchInput.value.trim() || "All";
  const lang = langSelect.value || "All";
  const minScore = scoreRange.value;
  const now = new Date().toISOString().slice(0, 19).replace("T", " ");

  let md = `# ScholarRepo-Finder Search Export\n`;
  md += `- **Query**: \`${query}\`\n`;
  md += `- **Filters**: Language: \`${lang}\`, Min Score: \`${minScore}\`, Paper Required: \`${paperCheck.checked}\`\n`;
  md += `- **Count**: ${repos.length} items\n`;
  md += `- **Exported At**: ${now}\n\n`;

  md += `| # | Repository | Score | Language | Paper/DOI | Last Updated | Description |\n`;
  md += `| :-: | :--- | :---: | :---: | :---: | :---: | :--- |\n`;

  repos.forEach((r, idx) => {
    const paperBadge = r.paper ? "✅ Yes" : "-";
    const desc = (r.desc || "").replace(/\|/g, "/");
    md += `| ${idx + 1} | [${r.id}](${r.url}) | **${r.score.toFixed(1)}** | \`${r.lang}\` | ${paperBadge} | ${r.updated} | ${desc} |\n`;
  });

  md += `\n---\n*Generated by [ScholarRepo-Finder](https://xzyozi.github.io/ScholarRepo-Finder/)*\n`;

  const blob = new Blob([md], { type: "text/markdown;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `scholar_repos_${new Date().toISOString().slice(0, 10)}.md`;
  a.click();
  URL.revokeObjectURL(url);

  showToast(t.downloadSuccess);
}

// 8. 個別引用コピー
window.copyItemMarkdown = function (repoId) {
  const t = I18N[currentLang];
  const repo = allRepos.find(r => r.id === repoId);
  if (!repo) return;

  const md = `- **[${repo.id}](${repo.url})** (Score: ${repo.score.toFixed(1)}, Lang: \`${repo.lang}\`)\n  - Description: ${repo.desc}\n  - Topics: \`${repo.topics.join(", ")}\`\n  - Paper/DOI: ${repo.paper ? "Yes" : "None"}`;

  navigator.clipboard.writeText(md).then(() => {
    showToast(`[${repo.name}] ${t.copySuccess}`);
  });
};

function showToast(message) {
  toastMsg.textContent = message;
  toast.classList.remove("translate-y-20", "opacity-0");
  setTimeout(() => {
    toast.classList.add("translate-y-20", "opacity-0");
  }, 2500);
}

// Event Listeners
searchInput.addEventListener("input", renderResults);
langSelect.addEventListener("change", renderResults);
scoreRange.addEventListener("input", (e) => {
  const t = I18N[currentLang];
  scoreVal.textContent = `${e.target.value}.0 ${t.scoreUnit}`;
  renderResults();
});
paperCheck.addEventListener("change", renderResults);
eduCheck.addEventListener("change", renderResults);
sortSelect.addEventListener("change", renderResults);
exportMdBtn.addEventListener("click", exportToMarkdown);

langToggleBtn.addEventListener("click", () => {
  currentLang = currentLang === "ja" ? "en" : "ja";
  localStorage.setItem("srf_lang", currentLang);
  applyI18n();
  renderResults();
  totalRepoCount.textContent = `${allRepos.length} ${I18N[currentLang].unitCount}`;
});

resetFiltersBtn.addEventListener("click", () => {
  const t = I18N[currentLang];
  searchInput.value = "";
  langSelect.value = "";
  scoreRange.value = "60";
  scoreVal.textContent = `60.0 ${t.scoreUnit}`;
  paperCheck.checked = false;
  eduCheck.checked = false;
  sortSelect.value = "score_desc";
  renderResults();
});

// Fallback Data
function getSampleFallbackData() {
  return [
    {
      id: "stanford-lab/cvrp-deep-solver",
      name: "cvrp-deep-solver",
      desc: "A benchmark deep reinforcement learning simulation toolkit for solving large-scale CVRP instances.",
      lang: "Python",
      topics: ["vehicle-routing", "reinforcement-learning", "simulation"],
      stars: 128,
      updated: "2024-05-10",
      score: 112.5,
      paper: true,
      edu: true,
      libs: ["numpy", "torch", "ortools"],
      url: "https://github.com/stanford-lab/cvrp-deep-solver"
    },
    {
      id: "mit-or/discrete-event-platform",
      name: "discrete-event-platform",
      desc: "High-performance discrete-event simulation platform for supply chain and manufacturing operations research.",
      lang: "Rust",
      topics: ["simulation", "operations-research", "discrete-event"],
      stars: 84,
      updated: "2024-04-22",
      score: 98.0,
      paper: true,
      edu: true,
      libs: ["ndarray"],
      url: "https://github.com/mit-or/discrete-event-platform"
    },
    {
      id: "Mominyar/emergency-dispatch-simulation-system",
      name: "emergency-dispatch-simulation-system",
      desc: "A turn-based emergency response dispatch simulation designed for algorithmic evaluation and baseline comparison.",
      lang: "C",
      topics: ["simulation", "dispatch", "c-programming"],
      stars: 15,
      updated: "2024-05-12",
      score: 85.5,
      paper: false,
      edu: true,
      libs: [],
      url: "https://github.com/Mominyar/emergency-dispatch-simulation-system"
    }
  ];
}

initApp();
