import { useEffect, useState } from "react";
import "./App.css";

const API_BASE = (import.meta.env.VITE_CRAWLER_API ??
  "http://localhost:8000") as string;

type Source = {
  id: string;
  name: string;
  url: string;
  category: string;
  enabled: boolean;
};

type Notice = {
  id: number;
  source_id: string;
  title: string;
  url: string;
  posted_at: string | null;
  summary: string | null;
  fetched_at: string;
};

type CrawlReport = {
  source_id: string;
  fetched: number;
  inserted: number;
  duplicates: number;
  errors: string[];
};

function App() {
  const [sources, setSources] = useState<Source[]>([]);
  const [activeSource, setActiveSource] = useState<string>("");
  const [notices, setNotices] = useState<Notice[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [crawling, setCrawling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastReports, setLastReports] = useState<CrawlReport[]>([]);

  const loadSources = async () => {
    const res = await fetch(`${API_BASE}/api/sources`);
    if (!res.ok) throw new Error(`sources ${res.status}`);
    const data: Source[] = await res.json();
    setSources(data);
  };

  const loadNotices = async (source: string) => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (source) qs.set("source", source);
      qs.set("limit", "50");
      const res = await fetch(`${API_BASE}/api/notices?${qs}`);
      if (!res.ok) throw new Error(`notices ${res.status}`);
      const data = await res.json();
      setNotices(data.items);
      setTotal(data.total);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const triggerCrawl = async () => {
    setCrawling(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (activeSource) qs.set("source", activeSource);
      const res = await fetch(`${API_BASE}/api/crawl?${qs}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`crawl ${res.status}`);
      const data: { reports: CrawlReport[] } = await res.json();
      setLastReports(data.reports);
      await loadNotices(activeSource);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCrawling(false);
    }
  };

  useEffect(() => {
    loadSources().catch((e) => setError((e as Error).message));
  }, []);

  useEffect(() => {
    loadNotices(activeSource).catch((e) => setError((e as Error).message));
  }, [activeSource]);

  return (
    <main className="feed">
      <header className="feed-head">
        <h1>학교 공지 AI · 크롤러 데모</h1>
        <p className="hint">
          이 화면은 <code>crawler</code> 모듈이 정상 동작하는지 확인하기 위한
          최소 UI입니다.
        </p>
      </header>

      <section className="controls">
        <label htmlFor="source-filter">출처</label>
        <select
          id="source-filter"
          value={activeSource}
          onChange={(e) => setActiveSource(e.target.value)}
        >
          <option value="">전체</option>
          {sources.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <button onClick={triggerCrawl} disabled={crawling}>
          {crawling ? "크롤 중..." : "지금 크롤링"}
        </button>
        <button onClick={() => loadNotices(activeSource)} disabled={loading}>
          새로고침
        </button>
        <span className="count">총 {total}건</span>
      </section>

      {error && <div className="error">에러: {error}</div>}

      {lastReports.length > 0 && (
        <details className="reports" open>
          <summary>최근 크롤 결과</summary>
          <ul>
            {lastReports.map((r) => (
              <li key={r.source_id}>
                <strong>{r.source_id}</strong> — fetched {r.fetched} / inserted{" "}
                {r.inserted} / dup {r.duplicates}
                {r.errors.length > 0 && (
                  <span className="warn"> · errors: {r.errors.join("; ")}</span>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}

      <ul className="notice-list">
        {notices.length === 0 && !loading && (
          <li className="empty">
            저장된 공지가 없습니다. 위의 <em>지금 크롤링</em> 버튼을 누르거나,
            터미널에서 <code>python -m app.runner crawl</code>을 실행하세요.
          </li>
        )}
        {notices.map((n) => (
          <li key={n.id}>
            <a href={n.url} target="_blank" rel="noreferrer">
              {n.title}
            </a>
            <div className="meta">
              <span className="src">{n.source_id}</span>
              {n.posted_at && <span className="date">{n.posted_at}</span>}
              {n.summary && <span className="summary">— {n.summary}</span>}
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}

export default App;
