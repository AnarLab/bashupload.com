"""Главная страница: загрузка из браузера (в т.ч. drag-and-drop)."""

from fastapi.responses import HTMLResponse

from app.config import BASE_URL, MAX_DOWNLOADS, TTL_SECONDS


def _ttl_human() -> str:
    s = TTL_SECONDS
    if s % 86400 == 0 and s >= 86400:
        n = s // 86400
        return f"{n} дн." if n != 1 else "1 день"
    if s % 3600 == 0 and s >= 3600:
        n = s // 3600
        return f"{n} ч."
    if s % 60 == 0:
        n = s // 60
        return f"{n} мин."
    return f"{s} с"


def home_page() -> HTMLResponse:
    ttl = _ttl_human()
    dl = "один раз" if MAX_DOWNLOADS <= 1 else f"до {MAX_DOWNLOADS} раз"
    base = BASE_URL.replace("&", "&amp;").replace('"', "&quot;")

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Загрузка файлов</title>
  <style>
    :root {{
      --bg: #0f1218;
      --surface: #171b24;
      --border: #2a3142;
      --text: #e8eaef;
      --muted: #8b93a7;
      --accent: #5b8cff;
      --accent-dim: #3d5a9e;
      --ok: #3ecf8e;
      --radius: 12px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: radial-gradient(1200px 600px at 20% -10%, #1a2340 0%, transparent 55%),
                  radial-gradient(900px 500px at 100% 0%, #152a38 0%, transparent 50%),
                  var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    .wrap {{
      max-width: 560px;
      margin: 0 auto;
      padding: 2.5rem 1.25rem 3rem;
    }}
    h1 {{
      font-size: 1.5rem;
      font-weight: 600;
      margin: 0 0 0.35rem;
      letter-spacing: -0.02em;
    }}
    .sub {{
      color: var(--muted);
      font-size: 0.9rem;
      margin-bottom: 1.75rem;
    }}
    .drop {{
      border: 2px dashed var(--border);
      border-radius: var(--radius);
      background: var(--surface);
      padding: 2.25rem 1.5rem;
      text-align: center;
      cursor: pointer;
      transition: border-color 0.2s, background 0.2s, transform 0.15s;
    }}
    .drop:hover, .drop.focus {{
      border-color: var(--accent-dim);
      background: #1a1f2a;
    }}
    .drop.drag {{
      border-color: var(--accent);
      background: #1c2433;
      transform: scale(1.01);
    }}
    .drop p {{ margin: 0; font-size: 0.95rem; }}
    .drop .hint {{ color: var(--muted); font-size: 0.85rem; margin-top: 0.5rem; }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      justify-content: center;
      margin-top: 1.25rem;
    }}
    button {{
      font: inherit;
      cursor: pointer;
      border: none;
      border-radius: 8px;
      padding: 0.55rem 1.1rem;
      background: var(--accent);
      color: #fff;
      font-weight: 500;
    }}
    button:disabled {{
      opacity: 0.45;
      cursor: not-allowed;
    }}
    button.secondary {{
      background: transparent;
      color: var(--muted);
      border: 1px solid var(--border);
    }}
    button.secondary:hover:not(:disabled) {{
      color: var(--text);
      border-color: var(--muted);
    }}
    #file {{ position: absolute; width: 0; height: 0; opacity: 0; pointer-events: none; }}
    .list {{
      margin-top: 1.25rem;
      font-size: 0.88rem;
      color: var(--muted);
      text-align: left;
      max-height: 160px;
      overflow-y: auto;
    }}
    .list li {{ margin: 0.25rem 0; word-break: break-all; }}
    .progress-wrap {{
      margin-top: 1rem;
      height: 6px;
      background: var(--border);
      border-radius: 3px;
      overflow: hidden;
      display: none;
    }}
    .progress-wrap.on {{ display: block; }}
    .progress-bar {{
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--accent-dim), var(--accent));
      transition: width 0.1s linear;
    }}
    .results {{
      margin-top: 1.75rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--border);
      display: none;
    }}
    .results.on {{ display: block; }}
    .results h2 {{ font-size: 1rem; margin: 0 0 0.75rem; color: var(--ok); }}
    .link-row {{
      display: flex;
      gap: 0.5rem;
      align-items: flex-start;
      margin-bottom: 0.65rem;
      flex-wrap: wrap;
    }}
    .link-row a {{
      color: var(--accent);
      word-break: break-all;
      flex: 1;
      min-width: 0;
    }}
    .link-row button.copy {{
      flex-shrink: 0;
      padding: 0.35rem 0.65rem;
      font-size: 0.8rem;
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--text);
    }}
    .link-row button.copy:hover {{ border-color: var(--accent-dim); }}
    .err {{
      margin-top: 1rem;
      padding: 0.75rem 1rem;
      background: #2a1818;
      border: 1px solid #5c2a2a;
      border-radius: 8px;
      color: #f0a8a8;
      font-size: 0.9rem;
      display: none;
    }}
    .err.on {{ display: block; }}
    code.cli {{
      display: block;
      margin-top: 1rem;
      padding: 0.85rem 1rem;
      background: #0a0c10;
      border-radius: 8px;
      font-size: 0.78rem;
      color: var(--muted);
      overflow-x: auto;
      border: 1px solid var(--border);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Загрузка файла</h1>
    <p class="sub">Файлы хранятся <strong>{ttl}</strong>, скачать можно <strong>{dl}</strong>. Публичный адрес ссылок: <strong>{base}</strong></p>

    <div class="drop" id="drop" tabindex="0" role="button" aria-label="Область загрузки">
      <p>Перетащите файлы сюда или нажмите «Выбрать»</p>
      <p class="hint">Можно несколько файлов за раз</p>
      <div class="actions">
        <button type="button" id="pick">Выбрать файлы</button>
        <button type="button" class="secondary" id="upload" disabled>Отправить</button>
      </div>
      <input type="file" id="file" multiple>
      <ul class="list" id="list" hidden></ul>
      <div class="progress-wrap" id="pwrap"><div class="progress-bar" id="pbar"></div></div>
    </div>

    <div class="err" id="err"></div>

    <div class="results" id="results">
      <h2>Готово</h2>
      <div id="links"></div>
      <code class="cli" id="cli"></code>
    </div>
  </div>
  <script>
(function () {{
  const drop = document.getElementById("drop");
  const file = document.getElementById("file");
  const pick = document.getElementById("pick");
  const uploadBtn = document.getElementById("upload");
  const list = document.getElementById("list");
  const pwrap = document.getElementById("pwrap");
  const pbar = document.getElementById("pbar");
  const err = document.getElementById("err");
  const results = document.getElementById("results");
  const linksEl = document.getElementById("links");
  const cliEl = document.getElementById("cli");

  let queue = [];

  function showErr(msg) {{
    err.textContent = msg;
    err.classList.add("on");
  }}
  function clearErr() {{
    err.classList.remove("on");
    err.textContent = "";
  }}

  function renderList() {{
    list.innerHTML = "";
    if (!queue.length) {{
      list.hidden = true;
      uploadBtn.disabled = true;
      return;
    }}
    list.hidden = false;
    uploadBtn.disabled = false;
    queue.forEach((f, i) => {{
      const li = document.createElement("li");
      li.textContent = f.name + " (" + (f.size < 1024 ? f.size + " B" : (f.size/1024|0) + " KB") + ")";
      list.appendChild(li);
    }});
  }}

  function addFiles(fileList) {{
    const arr = Array.from(fileList || []);
    if (!arr.length) return;
    queue = queue.concat(arr);
    renderList();
    clearErr();
    results.classList.remove("on");
  }}

  pick.addEventListener("click", () => file.click());
  drop.addEventListener("click", (e) => {{
    if (e.target === pick || e.target === uploadBtn || pick.contains(e.target) || uploadBtn.contains(e.target)) return;
    file.click();
  }});

  file.addEventListener("change", () => {{
    addFiles(file.files);
    file.value = "";
  }});

  ["dragenter", "dragover"].forEach((ev) => {{
    drop.addEventListener(ev, (e) => {{
      e.preventDefault();
      e.stopPropagation();
      drop.classList.add("drag");
    }});
  }});
  ["dragleave", "drop"].forEach((ev) => {{
    drop.addEventListener(ev, (e) => {{
      e.preventDefault();
      e.stopPropagation();
      if (ev !== "drop") drop.classList.remove("drag");
    }});
  }});
  drop.addEventListener("drop", (e) => {{
    drop.classList.remove("drag");
    addFiles(e.dataTransfer.files);
  }});

  drop.addEventListener("keydown", (e) => {{
    if (e.key === "Enter" || e.key === " ") {{ e.preventDefault(); file.click(); }}
  }});
  drop.addEventListener("focus", () => drop.classList.add("focus"));
  drop.addEventListener("blur", () => drop.classList.remove("focus"));

  function copyText(t, btn) {{
    navigator.clipboard.writeText(t).then(() => {{
      const o = btn.textContent;
      btn.textContent = "Скопировано";
      setTimeout(() => {{ btn.textContent = o; }}, 1500);
    }}).catch(() => {{}});
  }}

  uploadBtn.addEventListener("click", () => {{
    if (!queue.length) return;
    clearErr();
    results.classList.remove("on");
    linksEl.innerHTML = "";
    cliEl.textContent = "";

    const fd = new FormData();
    queue.forEach((f) => fd.append("file", f));

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/");
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (e) => {{
      if (!e.lengthComputable) return;
      pwrap.classList.add("on");
      pbar.style.width = Math.round((e.loaded / e.total) * 100) + "%";
    }};

    xhr.onload = () => {{
      pwrap.classList.remove("on");
      pbar.style.width = "0%";
      uploadBtn.disabled = false;
      pick.disabled = false;

      if (xhr.status >= 200 && xhr.status < 300) {{
        let data;
        try {{ data = JSON.parse(xhr.responseText); }} catch (e) {{
          showErr("Некорректный ответ сервера");
          return;
        }}
        if (!data.urls || !data.urls.length) {{
          showErr("Нет ссылок в ответе");
          return;
        }}
        queue = [];
        renderList();
        results.classList.add("on");
        data.urls.forEach((url) => {{
          const row = document.createElement("div");
          row.className = "link-row";
          const a = document.createElement("a");
          a.href = url;
          a.target = "_blank";
          a.rel = "noopener";
          a.textContent = url;
          const c = document.createElement("button");
          c.type = "button";
          c.className = "copy";
          c.textContent = "Копировать";
          c.addEventListener("click", () => copyText(url, c));
          row.appendChild(a);
          row.appendChild(c);
          linksEl.appendChild(row);
        }});
        cliEl.textContent = data.urls.map((u) => "curl -O " + u).join(String.fromCharCode(10));
      }} else {{
        let msg = "Ошибка " + xhr.status;
        try {{
          const j = JSON.parse(xhr.responseText);
          if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
        }} catch (e) {{}}
        showErr(msg);
      }}
    }};

    xhr.onerror = () => {{
      pwrap.classList.remove("on");
      pbar.style.width = "0%";
      uploadBtn.disabled = false;
      pick.disabled = false;
      showErr("Сеть недоступна или сервер не отвечает");
    }};

    uploadBtn.disabled = true;
    pick.disabled = true;
    xhr.send(fd);
  }});
}})();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
