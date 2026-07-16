import { Check, ChevronRight, FileText, Info, Layers3, LineChart, SlidersHorizontal } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

type Metric = { key: string; label: string; score: number; detail: string }
type Assessment = {
  id: string
  date: string
  version: number
  created_at: string
  source_event_ids: string[]
  assessment: { metrics: Metric[]; source_event_count: number; input_scope?: string }
}

type RangeDays = 7 | 30 | 90

const colors = ["#18181b", "#078161", "#c6631b", "#5b6474", "#a33352"]
const localToday = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai" }).format(new Date())
const moveDate = (date: string, days: number) => {
  const value = new Date(`${date}T12:00:00`)
  value.setDate(value.getDate() + days)
  return value.toISOString().slice(0, 10)
}
const labelDate = (date: string, long = false) => new Intl.DateTimeFormat("zh-CN", long ? { year: "numeric", month: "long", day: "numeric", weekday: "short" } : { month: "numeric", day: "numeric" }).format(new Date(`${date}T12:00:00`))

async function getJson<T>(url: string) {
  const response = await fetch(url)
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

function score(record: Assessment, key: string) { return record.assessment.metrics.find((metric) => metric.key === key)?.score ?? 0 }
function scoreClass(value: number) { return value >= 72 ? "text-emerald-700" : value >= 48 ? "text-amber-700" : "text-rose-700" }

export function AnalysisWorkspace() {
  const today = localToday()
  const [range, setRange] = useState<RangeDays>(30)
  const [startDate, setStartDate] = useState(moveDate(today, -29))
  const [endDate, setEndDate] = useState(today)
  const [records, setRecords] = useState<Assessment[]>([])
  const [selectedDate, setSelectedDate] = useState("")
  const [selectedKeys, setSelectedKeys] = useState<string[]>([])
  const [versions, setVersions] = useState<Assessment[]>([])
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading")
  const [error, setError] = useState("")

  const load = async (start = startDate, end = endDate) => {
    setStatus("loading")
    try {
      const next = await getJson<Assessment[]>(`/api/state-assessments?latest_per_day=1&start_date=${start}&end_date=${end}`)
      setRecords(next)
      setSelectedDate((current) => next.some((record) => record.date === current) ? current : (next.at(-1)?.date ?? ""))
      setSelectedKeys((current) => current.length ? current : (next.at(-1)?.assessment.metrics.slice(0, 3).map((metric) => metric.key) ?? []))
      setStatus("ready")
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "无法读取观察数据")
      setStatus("error")
    }
  }

  useEffect(() => { void load() }, [])
  useEffect(() => {
    if (!selectedDate) return setVersions([])
    void getJson<Assessment[]>(`/api/state-assessments?date=${selectedDate}`).then(setVersions).catch(() => setVersions([]))
  }, [selectedDate])

  const metrics = useMemo(() => records.at(-1)?.assessment.metrics ?? [], [records])
  const selectedIndex = records.findIndex((record) => record.date === selectedDate)
  const selected = selectedIndex >= 0 ? records[selectedIndex] : undefined
  const previous = selectedIndex > 0 ? records[selectedIndex - 1] : undefined
  const average = selected ? Math.round(selected.assessment.metrics.reduce((total, metric) => total + metric.score, 0) / Math.max(selected.assessment.metrics.length, 1)) : 0
  const activeMetrics = metrics.filter((metric) => selectedKeys.includes(metric.key))
  const width = 920
  const height = 276
  const chartTop = 18
  const chartBottom = 42
  const chartHeight = height - chartTop - chartBottom
  const point = (record: Assessment, index: number, key: string) => ({ x: records.length === 1 ? width / 2 : 8 + index * (width - 16) / (records.length - 1), y: chartTop + chartHeight - score(record, key) / 100 * chartHeight })

  const chooseRange = (days: RangeDays) => {
    const end = localToday()
    const start = moveDate(end, 1 - days)
    setRange(days); setStartDate(start); setEndDate(end)
    void load(start, end)
  }

  return <>
    <section className="border-b border-zinc-200 pb-8">
      <p className="text-xs font-semibold uppercase tracking-[.16em] text-emerald-700">Interpret & analyze</p>
      <div className="mt-3 flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
        <div><h1 className="max-w-2xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">把每天的表达，<br />放进一段连续的观察里。</h1><p className="mt-4 max-w-xl text-sm leading-6 text-zinc-600">这是对文本行为的长期观察，不构成医疗、心理或人格诊断。每一个结论都可以回看数据来源。</p></div>
        <div className="flex flex-wrap gap-2">{([7, 30, 90] as RangeDays[]).map((days) => <button key={days} onClick={() => chooseRange(days)} className={`rounded-md border px-3 py-2 text-sm ${range === days ? "border-zinc-950 bg-zinc-950 text-white" : "border-zinc-300 bg-white text-zinc-600 hover:border-zinc-600"}`}>近 {days} 天</button>)}<button title="按日期范围更新" onClick={() => void load()} className="rounded-md border border-zinc-300 bg-white p-2 text-zinc-700 hover:border-zinc-600"><SlidersHorizontal size={17} /></button></div>
      </div>
      <div className="mt-6 grid max-w-2xl gap-3 sm:grid-cols-2"><label className="text-xs font-medium text-zinc-600">开始日期<input type="date" value={startDate} max={endDate} onChange={(event) => { setStartDate(event.target.value); setRange(30) }} className="mt-2 block w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm" /></label><label className="text-xs font-medium text-zinc-600">结束日期<input type="date" value={endDate} min={startDate} onChange={(event) => { setEndDate(event.target.value); setRange(30) }} className="mt-2 block w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm" /></label></div>
    </section>
    {status === "loading" ? <p className="py-20 text-sm text-zinc-500">正在读取观察记录...</p> : status === "error" ? <p className="py-20 text-sm text-rose-700">读取失败：{error}</p> : !records.length ? <section className="py-20"><p className="text-xl font-semibold">这个区间还没有状态观察。</p><p className="mt-3 text-sm text-zinc-600">先在数据采集页清洗或确认当天文本，再留存一次观察。</p></section> : <>
      <section className="grid border-b border-zinc-200 py-8 lg:grid-cols-[1fr_18rem] lg:gap-12"><div><p className="text-sm font-medium text-zinc-500">所选日期</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">{selected && labelDate(selected.date, true)}</h2><div className="mt-7 flex items-end gap-5"><strong className={`text-6xl font-semibold tracking-tight ${scoreClass(average)}`}>{average}</strong><p className="mb-1 max-w-sm text-sm leading-6 text-zinc-600">当日多维观察均值。共依据 {selected?.assessment.source_event_count ?? 0} 条输入记录生成。</p></div></div><div className="mt-8 border-l-2 border-emerald-700 pl-4 lg:mt-1"><p className="text-xs font-semibold uppercase tracking-[.14em] text-emerald-700">Reading note</p><p className="mt-3 text-sm leading-6 text-zinc-700">先从变化看，而非给自己贴标签。点击趋势中的任意日期，可查看当日评估、依据和历史版本。</p></div></section>
      <section className="py-8"><div className="flex flex-col justify-between gap-5 lg:flex-row"><div><h2 className="text-xl font-semibold tracking-tight">多维趋势</h2><p className="mt-2 text-sm text-zinc-600">{records.length} 个有观察记录的日期，每天采用最新评估版本。</p></div><div className="flex flex-wrap gap-2">{metrics.map((metric, index) => { const active = selectedKeys.includes(metric.key); return <button key={metric.key} onClick={() => setSelectedKeys((keys) => active ? keys.filter((key) => key !== metric.key) : [...keys, metric.key])} className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-medium ${active ? "border-zinc-950 bg-zinc-950 text-white" : "border-zinc-300 bg-white text-zinc-600"}`}><span className="h-2 w-2 rounded-full" style={{ background: active ? colors[index % colors.length] : "#a1a1aa" }} />{metric.label}</button> })}</div></div>
        <div className="mt-7 overflow-x-auto border-y border-zinc-200 py-4"><svg viewBox={`0 0 ${width} ${height}`} className="min-w-[680px] w-full" role="img" aria-label="状态观察趋势，点击日期查看详情">{[0, 25, 50, 75, 100].map((value) => { const y = chartTop + chartHeight - value / 100 * chartHeight; return <g key={value}><line x1="8" x2={width - 8} y1={y} y2={y} stroke="#e4e4e7" /><text x={width - 8} y={y - 5} textAnchor="end" fill="#a1a1aa" fontSize="11">{value}</text></g> })}{activeMetrics.map((metric) => <polyline key={metric.key} points={records.map((record, index) => { const p = point(record, index, metric.key); return `${p.x},${p.y}` }).join(" ")} fill="none" stroke={colors[metrics.findIndex((item) => item.key === metric.key) % colors.length]} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />)}{records.map((record, index) => { const p = point(record, index, activeMetrics[0]?.key ?? metrics[0].key); const chosen = record.date === selectedDate; return <g key={record.id} onClick={() => setSelectedDate(record.date)} className="cursor-pointer"><line x1={p.x} x2={p.x} y1={chartTop} y2={chartTop + chartHeight} stroke={chosen ? "#18181b" : "transparent"} strokeDasharray="3 4" /><circle cx={p.x} cy={p.y} r={chosen ? 5 : 3} fill={chosen ? "#18181b" : "white"} stroke="#18181b" strokeWidth="2" /><text x={p.x} y={height - 14} textAnchor="middle" fill={chosen ? "#18181b" : "#71717a"} fontSize="11">{labelDate(record.date)}</text></g> })}</svg></div>
      </section>
      <section className="grid border-t border-zinc-200 py-8 lg:grid-cols-[1fr_19rem] lg:gap-12"><div><div className="flex items-center gap-2"><LineChart size={18} className="text-emerald-700" /><h2 className="text-xl font-semibold tracking-tight">当日解读</h2></div><div className="mt-5 divide-y divide-zinc-200 border-y border-zinc-200">{selected?.assessment.metrics.map((metric) => { const before = previous ? score(previous, metric.key) : undefined; const delta = before === undefined ? "区间内没有前一日可比较" : metric.score === before ? "与前一条观察持平" : `较前一条观察${metric.score > before ? "上升" : "下降"} ${Math.abs(metric.score - before)} 分`; return <article key={metric.key} className="grid gap-3 py-5 sm:grid-cols-[10rem_4.5rem_1fr] sm:items-center"><p className="font-medium">{metric.label}</p><strong className={`text-2xl font-semibold ${scoreClass(metric.score)}`}>{metric.score}</strong><div><p className="text-sm leading-6 text-zinc-700">{metric.detail}</p><p className="mt-1 text-xs text-zinc-500">{delta}</p></div></article> })}</div></div>
        <aside className="mt-8 lg:mt-0"><div className="border-b border-zinc-200 pb-5"><div className="flex items-center gap-2 text-sm font-medium"><FileText size={16} />评估证据</div><dl className="mt-4 space-y-3 text-sm"><div className="flex justify-between gap-4"><dt className="text-zinc-500">输入范围</dt><dd className="text-right">{selected?.assessment.input_scope ?? "公开事件"}</dd></div><div className="flex justify-between gap-4"><dt className="text-zinc-500">来源事件</dt><dd>{selected?.source_event_ids.length ?? 0} 条</dd></div><div className="flex justify-between gap-4"><dt className="text-zinc-500">当前版本</dt><dd>v{selected?.version}</dd></div><div className="flex justify-between gap-4"><dt className="text-zinc-500">生成时间</dt><dd>{selected?.created_at.slice(11, 16)}</dd></div></dl></div><div className="pt-5"><div className="flex items-center gap-2 text-sm font-medium"><Layers3 size={16} />同日历史版本</div><div className="mt-3 space-y-2">{versions.map((version) => <div key={version.id} className={`flex items-center justify-between border-l-2 py-2 pl-3 text-sm ${version.id === selected?.id ? "border-emerald-700" : "border-zinc-200"}`}><span>v{version.version} <span className="text-xs text-zinc-500">{version.created_at.slice(11, 16)}</span></span>{version.id === selected?.id && <Check size={15} className="text-emerald-700" />}</div>)}</div></div><a href={`/capture?date=${selectedDate}`} className="mt-6 flex items-center gap-1 text-sm font-medium text-emerald-700 hover:text-emerald-900">查看当天处理数据 <ChevronRight size={16} /></a></aside>
      </section>
      <section className="border-t border-zinc-200 py-6"><p className="flex items-start gap-2 text-xs leading-5 text-zinc-500"><Info size={15} className="mt-0.5 shrink-0" />评估分数用于比较同一人的文本表达趋势。输入量、写作场景和清洗版本变化，都可能影响结果。</p></section>
    </>}
  </>
}
