#!/usr/bin/env python3
"""Hermes Agent Evolution Tracker — data collection + HTML generation.

Collects five dimensions of agent evolution:
1. Skills — count, categories, creation/modification timeline
2. Memory — cognitive growth (user profile + environment knowledge)
3. Automation — cron jobs
4. Sessions — activity calendar, topics
5. Version — hermes-agent git release history

Generates a single self-contained dark-theme HTML dashboard.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────

HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))
SKILLS_DIR = HERMES_HOME / "skills"
MEMORY_FILE = HERMES_HOME / "memories" / "MEMORY.md"
USER_FILE = HERMES_HOME / "memories" / "USER.md"
SESSIONS_FILE = HERMES_HOME / "sessions" / "sessions.json"
CRON_DIR = HERMES_HOME / "cron"
REPO_DIR = Path(os.environ.get("HERMES_REPO", os.path.expanduser("~/VibeCoding/hermes-agent")))
HISTORY_FILE = Path(__file__).parent / "history.json"  # accumulates daily snapshots
OUTPUT_FILE = Path(__file__).parent / "index.html"
NOW = datetime.now(timezone.utc)

# ── Data Collection ─────────────────────────────────────────────────────────


def collect_skills():
    """Collect skills data: counts, categories, timeline."""
    skills = []
    categories = {}
    if not SKILLS_DIR.exists():
        return {"total": 0, "categories": {}, "skills": [], "timeline": []}

    for cat_dir in sorted(SKILLS_DIR.iterdir()):
        if not cat_dir.is_dir():
            continue
        cat_name = cat_dir.name
        cat_count = 0
        for skill_dir in cat_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    stat = skill_md.stat()
                    skills.append({
                        "name": skill_dir.name,
                        "category": cat_name,
                        "created": datetime.fromtimestamp(stat.st_birthtime, tz=timezone.utc).isoformat()
                        if hasattr(stat, 'st_birthtime')
                        else datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
                        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    })
                    cat_count += 1
        if cat_count:
            categories[cat_name] = cat_count

    # Build timeline: group skills by creation date
    timeline = {}
    for s in skills:
        date = s["created"][:10]
        timeline.setdefault(date, []).append(s["name"])

    return {
        "total": len(skills),
        "categories": dict(sorted(categories.items(), key=lambda x: x[1], reverse=True)),
        "skills": skills,
        "timeline": dict(sorted(timeline.items())),
    }


def collect_memory():
    """Collect memory entries."""
    result = {"user": [], "environment": [], "total": 0}
    for path, key in [(USER_FILE, "user"), (MEMORY_FILE, "environment")]:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            # Split by paragraph delimiter
            entries = [e.strip() for e in content.split("\n§\n") if e.strip()]
            result[key] = entries
            result["total"] += len(entries)
    return result


def collect_sessions():
    """Collect session history."""
    if not SESSIONS_FILE.exists():
        return {"total": 0, "sessions": [], "activity_days": {}}

    with open(SESSIONS_FILE) as f:
        sessions = json.load(f)

    activity_days = {}
    parsed = []
    for s in sessions:
        if isinstance(s, dict):
            start = s.get("session_start", "")
            title = s.get("title", "untitled")
        else:
            start = ""
            title = str(s)

        if start:
            day = start[:10]
            activity_days[day] = activity_days.get(day, 0) + 1
        parsed.append({"start": start, "title": title[:80]})

    return {
        "total": len(sessions),
        "sessions": parsed,
        "activity_days": dict(sorted(activity_days.items())),
    }


def collect_cron():
    """Collect cron jobs."""
    output_dir = CRON_DIR / "output"
    jobs = []
    if output_dir.exists():
        for f in output_dir.iterdir():
            if f.suffix == ".json":
                try:
                    data = json.loads(f.read_text())
                    jobs.append(data)
                except Exception:
                    pass
    return {"total": len(jobs), "jobs": jobs}


def collect_versions():
    """Collect hermes-agent version history from git tags."""
    if not (REPO_DIR / ".git").exists():
        return {"current": "unknown", "tags": [], "recent_commits": []}

    try:
        tags = subprocess.check_output(
            ["git", "tag", "--sort=-creatordate"],
            cwd=REPO_DIR, text=True
        ).strip().split("\n")
        tags = [t for t in tags if t.startswith("v")]
    except Exception:
        tags = []

    try:
        commits = subprocess.check_output(
            ["git", "log", "--oneline", "-10", "--format=%h %s (%ai)"],
            cwd=REPO_DIR, text=True
        ).strip().split("\n")
    except Exception:
        commits = []

    return {
        "current": tags[0] if tags else "unknown",
        "tags": tags[:30],
        "recent_commits": commits,
    }


# ── History Tracking ────────────────────────────────────────────────────────


def update_history(current_data):
    """Append today's snapshot to history.json for trend tracking."""
    today = NOW.strftime("%Y-%m-%d")
    history = {}
    if HISTORY_FILE.exists():
        history = json.loads(HISTORY_FILE.read_text())

    # If today already exists, update it
    history[today] = {
        "skills_total": current_data["skills"]["total"],
        "skills_categories": current_data["skills"]["categories"],
        "memory_total": current_data["memory"]["total"],
        "sessions_total": current_data["sessions"]["total"],
        "cron_total": current_data["cron"]["total"],
        "version": current_data["versions"]["current"],
        "timestamp": NOW.isoformat(),
    }
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))
    return history


# ── HTML Generation ──────────────────────────────────────────────────────────


def generate_html(data, history):
    """Generate a single self-contained dark-theme HTML dashboard."""
    skills_data = json.dumps(data["skills"])
    memory_data = json.dumps(data["memory"])
    sessions_data = json.dumps(data["sessions"])
    cron_data = json.dumps(data["cron"])
    versions_data = json.dumps(data["versions"])
    history_data = json.dumps(history)
    generated_at = NOW.strftime("%Y-%m-%d %H:%M UTC")

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hermes Agent · 进化日志</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
/* ── Reset & Base ── */
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{font-size:16px;scroll-behavior:smooth}}
body{{
  font-family:'SF Mono','JetBrains Mono','Fira Code',monospace;
  background:#0a0a0f;color:#c0c8d8;line-height:1.6;
  min-height:100vh;
  background-image:
    linear-gradient(rgba(0,255,136,.02) 1px,transparent 1px),
    linear-gradient(90deg,rgba(0,255,136,.02) 1px,transparent 1px);
  background-size:40px 40px;
}}

/* ── Header ── */
.header{{
  text-align:center;padding:3rem 1rem 2rem;
  border-bottom:1px solid rgba(0,255,136,.1);
  position:relative;overflow:hidden;
}}
.header::before{{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,transparent,#00ff88,transparent);
}}
.header h1{{
  font-size:2.2rem;font-weight:700;color:#e8eaf0;
  letter-spacing:-0.02em;
}}
.header h1 span{{color:#00ff88}}
.header .subtitle{{
  color:#6b7280;font-size:.9rem;margin-top:.5rem;
}}
.header .version-badge{{
  display:inline-block;margin-top:.8rem;padding:.25rem .75rem;
  background:rgba(0,255,136,.08);border:1px solid rgba(0,255,136,.2);
  border-radius:20px;color:#00ff88;font-size:.75rem;
}}

/* ── Layout ── */
.container{{max-width:1200px;margin:0 auto;padding:1.5rem}}
.grid-4{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2rem}}
@media(max-width:768px){{.grid-4{{grid-template-columns:repeat(2,1fr)}}}}
.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:1.5rem}}
@media(max-width:768px){{.grid-2{{grid-template-columns:1fr}}}}

/* ── KPI Cards ── */
.kpi-card{{
  background:#12121a;border:1px solid rgba(255,255,255,.06);
  border-radius:12px;padding:1.25rem;text-align:center;
  position:relative;overflow:hidden;transition:border-color .3s;
}}
.kpi-card:hover{{border-color:rgba(0,255,136,.25)}}
.kpi-card .icon{{font-size:1.5rem;margin-bottom:.25rem}}
.kpi-card .value{{
  font-size:2.2rem;font-weight:700;color:#00ff88;
  font-variant-numeric:tabular-nums;
}}
.kpi-card .label{{color:#6b7280;font-size:.8rem;margin-top:.25rem}}
.kpi-card .trend{{font-size:.7rem;margin-top:.25rem;color:#4b5563}}

/* ── Section Cards ── */
.section{{
  background:#12121a;border:1px solid rgba(255,255,255,.06);
  border-radius:12px;padding:1.5rem;margin-bottom:1.5rem;
}}
.section h2{{
  font-size:1.1rem;color:#e8eaf0;margin-bottom:1rem;
  padding-bottom:.75rem;border-bottom:1px solid rgba(255,255,255,.06);
  display:flex;align-items:center;gap:.5rem;
}}
.section h2 .dot{{
  width:8px;height:8px;border-radius:50%;
  background:#00ff88;box-shadow:0 0 8px #00ff88;
}}

/* ── Trend Chart ── */
.chart-wrap{{position:relative;height:280px}}
.chart-wrap canvas{{width:100%!important}}

/* ── Category Bars ── */
.cat-bar{{
  display:flex;align-items:center;gap:.75rem;margin-bottom:.5rem
}}
.cat-bar .cat-name{{
  width:160px;text-align:right;font-size:.8rem;color:#9ca3af;flex-shrink:0
}}
.cat-bar .cat-track{{
  flex:1;height:8px;background:rgba(255,255,255,.04);
  border-radius:4px;overflow:hidden
}}
.cat-bar .cat-fill{{
  height:100%;border-radius:4px;transition:width .6s;
  background:linear-gradient(90deg,#00ff88,#06b6d4);
}}
.cat-bar .cat-count{{
  font-size:.8rem;color:#00ff88;width:30px;flex-shrink:0
}}

/* ── Timeline ── */
.timeline-item{{
  display:flex;gap:1rem;padding:.6rem 0;border-left:2px solid rgba(0,255,136,.15);
  margin-left:.5rem;padding-left:1rem;position:relative;
}}
.timeline-item::before{{
  content:'';position:absolute;left:-5px;top:.85rem;
  width:8px;height:8px;border-radius:50%;
  background:#00ff88;box-shadow:0 0 6px #00ff88;
}}
.timeline-date{{color:#00ff88;font-size:.75rem;min-width:6rem;padding-top:.15rem}}
.timeline-content{{font-size:.8rem;color:#9ca3af}}
.timeline-content strong{{color:#e8eaf0}}

/* ── Memory Section ── */
.memory-block{{margin-bottom:1rem}}
.memory-block h3{{
  font-size:.85rem;color:#06b6d4;margin-bottom:.5rem
}}
.memory-item{{
  background:rgba(255,255,255,.02);border-radius:8px;
  padding:.75rem 1rem;margin-bottom:.4rem;font-size:.8rem;
  color:#9ca3af;line-height:1.5;
}}

/* ── Activity Grid ── */
.activity-legend{{
  display:flex;align-items:center;gap:.25rem;margin-bottom:1rem;
  font-size:.7rem;color:#6b7280;justify-content:flex-end
}}
.activity-legend span{{width:12px;height:12px;border-radius:2px;display:inline-block}}

/* ── Version Timeline ── */
.version-tag{{
  display:inline-flex;align-items:center;gap:.4rem;
  background:rgba(124,58,237,.1);border:1px solid rgba(124,58,237,.2);
  border-radius:6px;padding:.3rem .6rem;margin:.2rem;font-size:.75rem;
  color:#a78bfa;
}}
.version-tag.current{{
  background:rgba(0,255,136,.1);border-color:rgba(0,255,136,.3);
  color:#00ff88;
}}

/* ── Footer ── */
.footer{{
  text-align:center;padding:2rem 1rem;color:#4b5563;font-size:.75rem;
  border-top:1px solid rgba(255,255,255,.04);margin-top:1rem;
}}

/* ── Animations ── */
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.5}}}}
.pulse{{animation:pulse 2s infinite}}
</style>
</head>
<body>

<!-- ── Header ── -->
<header class="header">
  <h1>🧬 <span>Hermes Agent</span> · 进化日志</h1>
  <p class="subtitle">能力边界扩张 · 认知深度进化 · 自动化演进 · 每日自动更新</p>
  <span class="version-badge">v{data["versions"]["current"]}</span>
</header>

<div class="container">

<!-- ── KPI Dashboard ── -->
<div class="grid-4" id="kpi"></div>

<!-- ── Trend Chart ── -->
<div class="section">
  <h2><span class="dot pulse"></span>进化趋势</h2>
  <div class="chart-wrap"><canvas id="trendChart"></canvas></div>
</div>

<div class="grid-2">
  <!-- ── Skill Categories ── -->
  <div class="section" id="skill-cats">
    <h2><span class="dot"></span>技能类目分布</h2>
  </div>

  <!-- ── Recent Timeline ── -->
  <div class="section" id="timeline-sec">
    <h2><span class="dot"></span>近期进化事件</h2>
  </div>
</div>

<!-- ── Memory Evolution ── -->
<div class="section" id="memory-sec">
  <h2><span class="dot"></span>🧠 认知进化</h2>
</div>

<!-- ── Activity Calendar ── -->
<div class="section" id="activity-sec">
  <h2><span class="dot"></span>📅 活跃日历</h2>
  <div class="activity-legend">
    少<span style="background:#1a3a2a"></span><span style="background:#0e5c34"></span><span style="background:#0f9444"></span><span style="background:#00cf5d"></span><span style="background:#00ff88"></span>多
  </div>
  <div id="activity-grid" style="display:flex;flex-wrap:wrap;gap:3px"></div>
</div>

<!-- ── Version History ── -->
<div class="section">
  <h2><span class="dot"></span>⚙️ Hermes Agent 版本演进</h2>
  <div id="version-tags"></div>
</div>

<!-- ── Recent Commits ── -->
<div class="section" id="commits-sec">
  <h2><span class="dot"></span>🔧 最近提交</h2>
</div>

</div>

<footer class="footer">
  Generated at {generated_at} · Auto-updated daily at 00:00 CST · 
  <a href="https://github.com/Jason904/hermes-evolution" style="color:#00ff88;text-decoration:none">jason904/hermes-evolution</a>
</footer>

<script>
// ── Data ──
const SKILLS = {skills_data};
const MEMORY = {memory_data};
const SESSIONS = {sessions_data};
const CRON = {cron_data};
const VERSIONS = {versions_data};
const HISTORY = {history_data};

// ── KPI Cards ──
(function renderKPI() {{
  const kpi = document.getElementById('kpi');
  const cards = [
    {{icon:'🧩',value:SKILLS.total,label:'技能总数',trend:'覆盖 ' + Object.keys(SKILLS.categories).length + ' 个类目'}},
    {{icon:'🧠',value:MEMORY.total,label:'认知条目',trend:'用户画像 ' + MEMORY.user.length + ' · 环境 ' + MEMORY.environment.length}},
    {{icon:'💬',value:SESSIONS.total,label:'会话总数',trend:Object.keys(SESSIONS.activity_days).length + ' 个活跃日'}},
    {{icon:'🤖',value:CRON.total,label:'自动化任务',trend:CRON.total ? '已启用' : '待创建'}},
  ];
  kpi.innerHTML = cards.map(c=>`
    <div class="kpi-card">
      <div class="icon">${{c.icon}}</div>
      <div class="value">${{c.value}}</div>
      <div class="label">${{c.label}}</div>
      <div class="trend">${{c.trend}}</div>
    </div>`).join('');
}})();

// ── Trend Chart ──
(function renderTrend() {{
  const days = Object.keys(HISTORY).sort();
  if (days.length < 2) return;
  const ctx = document.getElementById('trendChart').getContext('2d');
  new Chart(ctx, {{
    type:'line',
    data:{{
      labels:days,
      datasets:[
        {{
          label:'技能总数',data:days.map(d=>HISTORY[d].skills_total||0),
          borderColor:'#00ff88',backgroundColor:'rgba(0,255,136,.05)',
          fill:true,tension:.4,pointRadius:3,pointBackgroundColor:'#00ff88'
        }},
        {{
          label:'认知条目',data:days.map(d=>HISTORY[d].memory_total||0),
          borderColor:'#7c3aed',backgroundColor:'rgba(124,58,237,.05)',
          fill:true,tension:.4,pointRadius:3,pointBackgroundColor:'#7c3aed'
        }},
        {{
          label:'会话总数',data:days.map(d=>HISTORY[d].sessions_total||0),
          borderColor:'#06b6d4',backgroundColor:'rgba(6,182,212,.05)',
          fill:true,tension:.4,pointRadius:3,pointBackgroundColor:'#06b6d4'
        }},
      ]
    }},
    options:{{
      responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{labels:{{color:'#9ca3af',font:{{family:'SF Mono'}}}}}}}},
      scales:{{
        x:{{ticks:{{color:'#6b7280'}},grid:{{color:'rgba(255,255,255,.03)'}}}},
        y:{{ticks:{{color:'#6b7280'}},grid:{{color:'rgba(255,255,255,.04)'}},beginAtZero:true}}
      }}
    }}
  }});
}})();

// ── Skill Categories ──
(function renderCategories() {{
  const cats = SKILLS.categories;
  const maxCount = Math.max(...Object.values(cats));
  const html = Object.entries(cats).map(([name,count])=>`
    <div class="cat-bar">
      <span class="cat-name">${{name.replace(/-/g,' ')}}</span>
      <span class="cat-track"><span class="cat-fill" style="width:${{(count/maxCount*100).toFixed(0)}}%"></span></span>
      <span class="cat-count">${{count}}</span>
    </div>`).join('');
  document.getElementById('skill-cats').innerHTML += html;
}})();

// ── Timeline ──
(function renderTimeline() {{
  const timeline = SKILLS.timeline;
  const dates = Object.keys(timeline).sort().reverse().slice(0, 10);
  const html = dates.map(date=>`
    <div class="timeline-item">
      <span class="timeline-date">${{date}}</span>
      <span class="timeline-content">
        新增技能: <strong>${{timeline[date].slice(0,6).join('</strong>, <strong>')}}</strong>
        ${{timeline[date].length > 6 ? ' …等 '+timeline[date].length+' 个' : ''}}
      </span>
    </div>`).join('');
  document.getElementById('timeline-sec').innerHTML += html || '<p style="color:#6b7280;font-size:.8rem">暂无数据</p>';
}})();

// ── Memory ──
(function renderMemory() {{
  let html = '';
  if (MEMORY.user.length) {{
    html += '<div class="memory-block"><h3>👤 用户画像</h3>';
    html += MEMORY.user.map(e=>`<div class="memory-item">${{e}}</div>`).join('');
    html += '</div>';
  }}
  if (MEMORY.environment.length) {{
    html += '<div class="memory-block"><h3>🌍 环境认知</h3>';
    html += MEMORY.environment.map(e=>`<div class="memory-item">${{e}}</div>`).join('');
    html += '</div>';
  }}
  document.getElementById('memory-sec').innerHTML += html || '<p style="color:#6b7280;font-size:.8rem">暂无认知数据</p>';
}})();

// ── Activity Calendar (GitHub-style) ──
(function renderActivity() {{
  const grid = document.getElementById('activity-grid');
  const days = SESSIONS.activity_days;
  const dayKeys = Object.keys(days);
  if (!dayKeys.length) {{
    grid.innerHTML = '<span style="color:#6b7280;font-size:.8rem">暂无活动</span>';
    return;
  }}
  // Show last 90 days
  const now = new Date();
  const cells = [];
  for (let i = 89; i >= 0; i--) {{
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0,10);
    const count = days[key] || 0;
    let color = '#1a1a24';
    if (count > 0) color = '#1a3a2a';
    if (count >= 3) color = '#0e5c34';
    if (count >= 6) color = '#0f9444';
    if (count >= 10) color = '#00cf5d';
    if (count >= 15) color = '#00ff88';
    cells.push(`<span title="${{key}}: ${{count}} sessions"
      style="width:12px;height:12px;border-radius:2px;background:${{color}};display:inline-block"></span>`);
  }}
  grid.innerHTML = cells.join('');
}})();

// ── Version Tags ──
(function renderVersions() {{
  const tags = VERSIONS.tags;
  const current = VERSIONS.current;
  document.getElementById('version-tags').innerHTML = tags.map(t=>
    `<span class="version-tag${{t===current?' current':''}}">${{t===current?'⚡ ':''}}${{t}}</span>`
  ).join('');
}})();

// ── Recent Commits ──
(function renderCommits() {{
  const commits = VERSIONS.recent_commits;
  document.getElementById('commits-sec').innerHTML += commits.map(c=>`
    <div class="timeline-item" style="border-left-color:rgba(124,58,237,.15)">
      <span class="timeline-content" style="font-size:.75rem">${{c}}</span>
    </div>`).join('');
}})();
</script>

</body>
</html>'''
    return html


# ── Main ────────────────────────────────────────────────────────────────────


def main():
    print("🔍 Collecting evolution data...")
    data = {
        "skills": collect_skills(),
        "memory": collect_memory(),
        "sessions": collect_sessions(),
        "cron": collect_cron(),
        "versions": collect_versions(),
    }

    print(f"   Skills: {data['skills']['total']} in {len(data['skills']['categories'])} categories")
    print(f"   Memory: {data['memory']['total']} entries")
    print(f"   Sessions: {data['sessions']['total']}")
    print(f"   Cron jobs: {data['cron']['total']}")
    print(f"   Version: {data['versions']['current']}")

    print("📝 Updating history...")
    history = update_history(data)

    print("🎨 Generating HTML...")
    html = generate_html(data, history)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"   ✅ Written to {OUTPUT_FILE} ({len(html):,} bytes)")

    # Also save raw data for potential use
    data_file = Path(__file__).parent / "data.json"
    data_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    return data


if __name__ == "__main__":
    main()
