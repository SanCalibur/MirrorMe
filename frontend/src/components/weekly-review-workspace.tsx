import { CheckCircle2, ClipboardList, Plus, RotateCcw, TrendingDown, TrendingUp } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

type Metric = { key: string; label: string; average: number; latest: number; change: number }
type Review = { start_date: string; end_date: string; data_quality: "sufficient" | "limited"; headline: string; observed_days: number; usable_days: number; average_confidence: number; metrics: Metric[]; feedback: Record<string, number> }
type Action = { id: string; week_start: string; title: string; completed_at: string | null }

const today = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai" }).format(new Date())
const monday = (value: string) => { const date = new Date(`${value}T12:00:00`); const day = (date.getDay() + 6) % 7; date.setDate(date.getDate() - day); return date.toISOString().slice(0, 10) }
async function request<T>(url: string, init?: RequestInit) { const response = await fetch(url, init); if (!response.ok) throw new Error(await response.text()); return response.json() as Promise<T> }

export function WeeklyReviewWorkspace() {
  const [endDate, setEndDate] = useState(today())
  const [review, setReview] = useState<Review | null>(null)
  const [actions, setActions] = useState<Action[]>([])
  const [draft, setDraft] = useState("")
  const [status, setStatus] = useState("正在读取本周观察与行动。")
  const weekStart = review?.start_date ?? monday(endDate)
  const load = async (date = endDate) => {
    setStatus("正在读取本周观察与行动。")
    try {
      const next = await request<Review>(`/api/weekly-review?end_date=${date}`)
      setReview(next)
      setActions(await request<Action[]>(`/api/actions?week_start=${next.start_date}`))
      setStatus("")
    } catch (error) { setStatus(error instanceof Error ? `读取失败：${error.message}` : "读取失败。") }
  }
  useEffect(() => { void load(endDate) }, [endDate])
  const completed = useMemo(() => actions.filter(item => item.completed_at).length, [actions])
  const add = async () => {
    if (!draft.trim()) return
    try {
      const action = await request<Action>("/api/actions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ week_start: weekStart, title: draft, source: "weekly-review" }) })
      setActions(current => [...current, action]); setDraft("")
    } catch (error) { setStatus(error instanceof Error ? `保存失败：${error.message}` : "保存失败。") }
  }
  const toggle = async (action: Action) => {
    try {
      const next = await request<Action>(`/api/actions/${action.id}/toggle`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ completed: !action.completed_at }) })
      setActions(current => current.map(item => item.id === next.id ? next : item))
    } catch (error) { setStatus(error instanceof Error ? `更新失败：${error.message}` : "更新失败。") }
  }
  return <>
    <section className="border-b border-zinc-200 pb-8"><p className="text-xs font-semibold uppercase tracking-[.16em] text-emerald-700">Weekly reflection</p><div className="mt-3 flex flex-col justify-between gap-5 sm:flex-row sm:items-end"><div><h1 className="text-4xl font-semibold tracking-tight">看见一周的变化，<br />再把它变成下一步。</h1><p className="mt-4 max-w-2xl text-sm leading-6 text-zinc-600">周回顾只汇总已留存的 LLM 每日观察，不把它当作人格或健康诊断。缺少足够样本时，会保留不确定性。</p></div><label className="text-sm text-zinc-600">截至日期<input type="date" value={endDate} onChange={event => setEndDate(event.target.value)} className="mt-2 block rounded-md border border-zinc-300 bg-white px-3 py-2" /></label></div></section>
    {review && <><section className="grid gap-4 border-b border-zinc-200 py-8 lg:grid-cols-[1.35fr_.65fr]"><div className="border-l-4 border-emerald-700 bg-white p-6"><p className="text-xs font-semibold uppercase tracking-[.14em] text-emerald-700">{review.start_date} - {review.end_date}</p><h2 className="mt-3 text-2xl font-semibold tracking-tight">{review.headline}</h2><p className="mt-4 text-sm leading-6 text-zinc-600">覆盖 {review.observed_days} 天观察，其中 {review.usable_days} 天达到质量门槛；平均置信度 {Math.round(review.average_confidence * 100)}%。</p></div><div className={`border p-6 ${review.data_quality === "sufficient" ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}><p className="text-sm font-medium">观察校准</p><dl className="mt-4 space-y-2 text-sm text-zinc-700"><div className="flex justify-between"><dt>准确</dt><dd>{review.feedback.accurate ?? 0}</dd></div><div className="flex justify-between"><dt>不准确</dt><dd>{review.feedback.inaccurate ?? 0}</dd></div><div className="flex justify-between"><dt>不确定</dt><dd>{review.feedback.uncertain ?? 0}</dd></div></dl></div></section>
      <section className="py-8"><div className="flex items-center gap-2"><ClipboardList size={18} className="text-emerald-700" /><h2 className="text-xl font-semibold">本周维度变化</h2></div>{review.metrics.length ? <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{review.metrics.map(metric => { const rising = metric.change >= 0; const inverse = metric.key === "pressure_load"; const positive = inverse ? !rising : rising; return <article key={metric.key} className="border border-zinc-200 bg-white p-5"><div className="flex items-start justify-between gap-3"><p className="font-medium">{metric.label}</p><span className={`flex items-center gap-1 text-xs font-medium ${positive ? "text-emerald-700" : "text-amber-700"}`}>{rising ? <TrendingUp size={15} /> : <TrendingDown size={15} />}{metric.change > 0 ? "+" : ""}{metric.change}</span></div><p className="mt-5 text-3xl font-semibold">{metric.latest}</p><p className="mt-2 text-xs text-zinc-500">本周均值 {metric.average}，与本周首个可用观察相比。</p></article> })}</div> : <p className="mt-5 text-sm text-zinc-500">暂无可聚合的维度数据。先完成几天的清洗、确认与 LLM 观察。</p>}</section>
      <section className="grid gap-7 border-t border-zinc-200 py-8 lg:grid-cols-[.7fr_1.3fr]"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-emerald-700">Action loop</p><h2 className="mt-2 text-2xl font-semibold tracking-tight">给下一周留一件<br />具体、可完成的事。</h2><p className="mt-4 text-sm leading-6 text-zinc-600">行动不由模型自动决定。你可以从趋势中挑选真正愿意验证的一步。</p></div><div className="border border-zinc-200 bg-white p-5"><div className="flex items-center justify-between"><p className="font-medium">本周行动</p><span className="text-xs text-zinc-500">完成 {completed} / {actions.length}</span></div><div className="mt-4 flex gap-2"><input value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === "Enter") void add() }} maxLength={300} placeholder="例如：每天开始工作前写下一个明确下一步" className="min-w-0 flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm" /><button onClick={() => void add()} title="添加行动" className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-zinc-950 text-white"><Plus size={18} /></button></div><div className="mt-4 divide-y divide-zinc-100">{actions.map(action => <div key={action.id} className="flex items-center gap-3 py-3"><button onClick={() => void toggle(action)} title={action.completed_at ? "标为未完成" : "标为完成"} className={`grid h-7 w-7 shrink-0 place-items-center rounded-full border ${action.completed_at ? "border-emerald-700 bg-emerald-700 text-white" : "border-zinc-300 text-zinc-400"}`}>{action.completed_at ? <CheckCircle2 size={16} /> : <RotateCcw size={14} />}</button><p className={`text-sm ${action.completed_at ? "text-zinc-400 line-through" : "text-zinc-800"}`}>{action.title}</p></div>)}{!actions.length && <p className="py-5 text-sm text-zinc-500">还没有行动项。</p>}</div></div></section></>}
    <p className="pb-8 text-xs text-zinc-500" aria-live="polite">{status}</p>
  </>
}
