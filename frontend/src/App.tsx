import { BarChart3, Database, KeyRound, Settings2, SlidersHorizontal } from "lucide-react"
import { useEffect, useState } from "react"
import { AnalysisWorkspace } from "./components/analysis-workspace"
import { Card, CardContent } from "./components/ui/card"

const pages = [{ href: "/capture", label: "数据采集", icon: Database }, { href: "/analysis", label: "数据解读", icon: BarChart3 }, { href: "/settings", label: "设置", icon: Settings2 }]
const date = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai" }).format(new Date())
const captureDate = () => new URLSearchParams(window.location.search).get("date") || date()
async function api<T>(url: string, init?: RequestInit) { const r = await fetch(url, init); if (!r.ok) throw new Error(await r.text()); return r.json() as Promise<T> }

const DEFAULT_CLEANING_PROMPT = "你是文本清洗助手。仅输出清洗后的原文，不要解释。保留原意、事实、专有名词、数字、时间顺序和不确定性；修正明显空白、断句、重复片段、口语填充词与标点。不要总结、扩写、改写立场或编造内容。"
const DEFAULT_OBSERVATION_PROMPT = "基于当天已清洗文本做审慎的状态观察。重点评估表达准确性、思路组织、情绪语气、压力负荷、行动推进和社交取向；每项必须引用具体文本证据，并明确不确定性。避免诊断、标签化或超出文本的推断。"

function Shell({ children }: { children: React.ReactNode }) {
  const path = window.location.pathname === "/" ? "/capture" : window.location.pathname
  return <div className="min-h-screen bg-zinc-50 text-zinc-950"><header className="border-b border-zinc-200 bg-white"><div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4"><a href="/capture" className="font-semibold tracking-tight">MirrorMe</a><nav className="flex gap-1">{pages.map(({ href, label, icon: Icon }) => <a key={href} href={href} className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${path === href ? "bg-zinc-950 text-white" : "text-zinc-500 hover:bg-zinc-100"}`}><Icon size={15} />{label}</a>)}</nav></div></header><main className="mx-auto max-w-6xl px-6 py-10">{children}</main></div>
}

function Capture() {
  const [daily, setDaily] = useState(captureDate()); const [events, setEvents] = useState<Array<{ id: string; created_at: string; redacted: string; project: string | null; tags: string[]; is_private: boolean }>>([]); const [cleaned, setCleaned] = useState(""); const [documentId, setDocumentId] = useState(""); const [accepted, setAccepted] = useState(false); const [message, setMessage] = useState("选择日期后读取数据")
  const load = async () => { const rows = await api<typeof events>(`/api/events?date=${daily}&include_private=1`); setEvents(rows) }
  useEffect(() => { void load() }, [daily])
  const cleanDaily = async () => { const api_url = sessionStorage.getItem("llm_url") || ""; const api_key = sessionStorage.getItem("llm_key") || ""; const model = sessionStorage.getItem("llm_model") || ""; const prompt = sessionStorage.getItem("llm_prompt") || ""; setMessage("正在合并并清洗当天公开事件"); const result = await api<{ output: string; source_event_count: number; composed_event_count: number; document: { id: string } }>("/api/daily/llm-clean", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ date: daily, api_url, api_key, model, prompt }) }); setCleaned(result.output); setDocumentId(result.document.id); setAccepted(false); setMessage(`已将 ${result.source_event_count} 条原始提交合并为 ${result.composed_event_count} 段，再保存清洗草稿`) }
  const accept = async () => { if (!documentId) return; await api(`/api/cleaned-documents/${documentId}/accept`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); setAccepted(true); setMessage("已接受此清洗版本。下一步可手动触发 LLM 观察并留存。") }
  const observeWithLlm = async () => { if (!documentId || !accepted) return; const api_url = sessionStorage.getItem("llm_url") || ""; const api_key = sessionStorage.getItem("llm_key") || ""; const model = sessionStorage.getItem("llm_model") || ""; const prompt = sessionStorage.getItem("llm_observation_prompt") || ""; setMessage("正在用 LLM 对已接受的清洗文本进行结构化观察"); const result = await api<{ assessment: { summary: string } }>("/api/state-assessments/llm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ document_id: documentId, api_url, api_key, model, prompt }) }); setMessage(`已留存 LLM 观察：${result.assessment.summary}`) }
  return <Shell><p className="text-xs font-semibold uppercase tracking-[.15em] text-emerald-700">Capture & process</p><h1 className="mt-2 text-4xl font-semibold tracking-tight">先整理当天数据，<br />再把它交给分析。</h1><div className="mt-8 grid gap-4 lg:grid-cols-[1.3fr_.7fr]"><Card><CardContent><div className="flex items-center justify-between"><p className="text-sm font-medium">{daily} 的数据库数据</p><span className="text-xs text-zinc-500">{events.length} 条</span></div><div className="mt-4 max-h-80 overflow-auto">{events.map(event => <article key={event.id} className="border-t border-zinc-100 py-3"><p className="text-xs text-zinc-500">{event.created_at.slice(11, 19)} · {event.project || "未归档"} · {event.is_private ? "私密" : "公开"}</p><p className="mt-1 text-sm leading-6">{event.redacted}</p></article>) || <p className="text-sm text-zinc-500">没有数据</p>}</div></CardContent></Card><div className="grid gap-4"><Card><CardContent><p className="text-sm font-medium">选择日期</p><input value={daily} onChange={e => setDaily(e.target.value)} type="date" className="mt-4 w-full rounded-lg border border-zinc-200 p-2" /><button onClick={() => void cleanDaily()} className="mt-4 w-full rounded-lg bg-zinc-950 px-3 py-2 text-sm text-white">LLM 清洗当天数据</button><p className="mt-2 text-xs leading-5 text-zinc-500">仅发送公开事件。推荐使用本地 LLM 进行清洗和观察。</p></CardContent></Card><details className="rounded-xl border border-zinc-200 bg-white p-5"><summary className="cursor-pointer text-sm font-medium">手动补充当天内容</summary><p className="mt-2 text-sm text-zinc-500">低频使用。</p></details></div></div>{cleaned && <Card className="mt-4"><CardContent><div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm font-medium">清洗草稿，可分析文本</p><div className="flex gap-2">{!accepted && <button onClick={() => void accept()} className="rounded-lg border border-zinc-300 px-3 py-2 text-sm">接受清洗版本</button>}{accepted && <button onClick={() => void observeWithLlm()} className="rounded-lg bg-zinc-950 px-3 py-2 text-sm text-white">LLM 观察并留存</button>}</div></div><p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-zinc-700">{cleaned}</p></CardContent></Card>}<p className="mt-4 text-sm text-zinc-500">{message}</p></Shell>
}

function Analysis() { return <Shell><AnalysisWorkspace /></Shell> }

function Settings() { const [url, setUrl] = useState(sessionStorage.getItem("llm_url") || ""); const [model, setModel] = useState(sessionStorage.getItem("llm_model") || ""); const [key, setKey] = useState(sessionStorage.getItem("llm_key") || ""); const [cleaningPrompt, setCleaningPrompt] = useState(sessionStorage.getItem("llm_prompt") || "只输出清洗后的原文。保留原意、事实、专有名词、数字和不确定性；修正明显空白、断句、重复片段、填充词和标点。不要总结、扩写或编造。"); const [observationPrompt, setObservationPrompt] = useState(sessionStorage.getItem("llm_observation_prompt") || "重点关注表达是否清晰、压力线索的语境、行动推进与不确定性。引用具体文本证据，避免过度推断。"); const save = () => { sessionStorage.setItem("llm_url", url); sessionStorage.setItem("llm_model", model); sessionStorage.setItem("llm_key", key); sessionStorage.setItem("llm_prompt", cleaningPrompt); sessionStorage.setItem("llm_observation_prompt", observationPrompt) }; return <Shell><p className="text-xs font-semibold uppercase tracking-[.15em] text-emerald-700">Rules & API</p><h1 className="mt-2 text-4xl font-semibold tracking-tight">设置规则，<br />再决定如何处理数据。</h1><div className="mt-8 grid gap-4 lg:grid-cols-2"><Card><CardContent><KeyRound /><h2 className="mt-4 font-medium">LLM API 与提示词</h2><div className="mt-4 grid gap-3"><input value={url} onChange={e => setUrl(e.target.value)} className="rounded-lg border border-zinc-200 p-3" placeholder="API URL" /><input value={model} onChange={e => setModel(e.target.value)} className="rounded-lg border border-zinc-200 p-3" placeholder="Model" /><input value={key} onChange={e => setKey(e.target.value)} type="password" className="rounded-lg border border-zinc-200 p-3" placeholder="API Key（仅当前浏览器会话）" /><label className="text-xs text-zinc-500">清洗提示词<textarea value={cleaningPrompt} onChange={e => setCleaningPrompt(e.target.value)} rows={5} className="mt-1 rounded-lg border border-zinc-200 p-3" placeholder="LLM 清洗提示词" /></label><label className="text-xs text-zinc-500">每日观察提示词<textarea value={observationPrompt} onChange={e => setObservationPrompt(e.target.value)} rows={7} className="mt-1 rounded-lg border border-zinc-200 p-3" placeholder="LLM 每日观察提示词" /></label></div><button onClick={save} className="mt-4 rounded-lg bg-zinc-950 px-4 py-2 text-sm text-white">保存会话设置</button></CardContent></Card><Card><CardContent><SlidersHorizontal /><h2 className="mt-4 font-medium">观察边界</h2><p className="mt-5 text-sm leading-6 text-zinc-700">LLM 观察只会在你手动确认清洗稿并点击“LLM 观察并留存”时运行。它必须返回结构化维度、文本证据与置信度。</p><p className="mt-6 text-sm leading-6 text-zinc-500">仅发送公开事件形成的已接受清洗文本。推荐使用本地 LLM；API Key 仅保存在当前浏览器会话，不写入 SQLite。</p></CardContent></Card></div></Shell> }
void Settings

function BatchSettings() {
  const [url, setUrl] = useState(sessionStorage.getItem("llm_url") || "")
  const [model, setModel] = useState(sessionStorage.getItem("llm_model") || "")
  const [key, setKey] = useState(sessionStorage.getItem("llm_key") || "")
  const [cleaningPrompt, setCleaningPrompt] = useState(sessionStorage.getItem("llm_prompt") || DEFAULT_CLEANING_PROMPT)
  const [observationPrompt, setObservationPrompt] = useState(sessionStorage.getItem("llm_observation_prompt") || DEFAULT_OBSERVATION_PROMPT)
  const [message, setMessage] = useState("保存配置后，可手动批量处理所有尚未观察的公开日期。")
  const [running, setRunning] = useState(false)
  const save = () => {
    sessionStorage.setItem("llm_url", url)
    sessionStorage.setItem("llm_model", model)
    sessionStorage.setItem("llm_key", key)
    sessionStorage.setItem("llm_prompt", cleaningPrompt)
    sessionStorage.setItem("llm_observation_prompt", observationPrompt)
    setMessage("已保存至当前浏览器会话。")
  }
  const runBatch = async () => {
    if (!url || !model) { setMessage("请先填写 API URL 与模型并保存。 "); return }
    setRunning(true)
    setMessage("正在逐日清洗并生成 LLM 观察；这可能需要一些时间。")
    try {
      const result = await api<{ processed: Array<{ date: string }>; skipped: string[]; failed: Array<{ date: string; error: string }> }>("/api/state-assessments/llm/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_url: url, api_key: key, model, cleaning_prompt: cleaningPrompt, prompt: observationPrompt }),
      })
      const failed = result.failed.length ? `；失败 ${result.failed.map(item => item.date).join("、")}` : ""
      setMessage(`完成：新增 ${result.processed.length} 天，跳过 ${result.skipped.length} 天${failed}。`)
    } catch (error) {
      setMessage(error instanceof Error ? `批处理失败：${error.message}` : "批处理失败。")
    } finally { setRunning(false) }
  }
  return <Shell>
    <p className="text-xs font-semibold uppercase tracking-[.15em] text-emerald-700">Rules & API</p>
    <h1 className="mt-2 text-4xl font-semibold tracking-tight">设置规则，<br />再决定如何处理数据。</h1>
    <div className="mt-8 grid gap-4 lg:grid-cols-2">
      <Card><CardContent><KeyRound /><h2 className="mt-4 font-medium">LLM API 与提示词</h2><div className="mt-4 grid gap-3"><input value={url} onChange={e => setUrl(e.target.value)} className="rounded-lg border border-zinc-200 p-3" placeholder="API URL" /><input value={model} onChange={e => setModel(e.target.value)} className="rounded-lg border border-zinc-200 p-3" placeholder="Model" /><input value={key} onChange={e => setKey(e.target.value)} type="password" className="rounded-lg border border-zinc-200 p-3" placeholder="API Key（仅当前浏览器会话）" /><label className="text-xs text-zinc-500">清洗提示词<textarea value={cleaningPrompt} onChange={e => setCleaningPrompt(e.target.value)} rows={5} className="mt-1 w-full rounded-lg border border-zinc-200 p-3" /></label><label className="text-xs text-zinc-500">每日观察提示词<textarea value={observationPrompt} onChange={e => setObservationPrompt(e.target.value)} rows={7} className="mt-1 w-full rounded-lg border border-zinc-200 p-3" /></label></div><button onClick={save} className="mt-4 rounded-lg bg-zinc-950 px-4 py-2 text-sm text-white">保存会话设置</button></CardContent></Card>
      <Card><CardContent><SlidersHorizontal /><h2 className="mt-4 font-medium">全库数据处理</h2><p className="mt-5 text-sm leading-6 text-zinc-700">按公开输入的日期依次清洗、接受清洗稿并生成 LLM 观察。已有 LLM 观察的日期会跳过；单日失败不会影响其它日期。</p><button disabled={running} onClick={() => void runBatch()} className="mt-5 w-full rounded-lg bg-zinc-950 px-4 py-3 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50">{running ? "正在批量处理..." : "批量处理全部未观察日期"}</button><p className="mt-3 text-xs leading-5 text-zinc-500">将把所有尚未生成 LLM 观察的公开日期发送至当前配置的 LLM。推荐使用本地 LLM；API Key 仅保存在当前浏览器会话，不写入 SQLite。</p><p className="mt-5 border-t border-zinc-100 pt-4 text-sm text-zinc-600" aria-live="polite">{message}</p></CardContent></Card>
    </div>
  </Shell>
}

export default function App() { const path = window.location.pathname; return path === "/analysis" || path === "/state" ? <Analysis /> : path === "/settings" ? <BatchSettings /> : <Capture /> }
