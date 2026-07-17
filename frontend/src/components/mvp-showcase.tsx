import { Activity, Brain, CalendarDays, ChevronLeft, ChevronRight, CircleAlert, Gauge, LockKeyhole, MessageSquare, Sparkles, Target, TrendingDown, TrendingUp } from "lucide-react"
import { useMemo, useState } from "react"

type MetricKey = "clarity" | "organization" | "affect" | "pressure" | "action" | "social"
type DemoDay = { date: string; inputs: number; confidence: number; summary: string; evidence: string; nextStep: string; scores: Record<MetricKey, number> }

const metrics: Array<{ key: MetricKey; label: string; short: string; description: string; positiveWhen: "higher" | "lower"; evidenceLens: string }> = [
  { key: "clarity", label: "表达清晰", short: "清晰", description: "判断、边界、因果和下一步是否说得明确。", positiveWhen: "higher", evidenceLens: "查找明确判断、限定条件与行动对象。" },
  { key: "organization", label: "思路组织", short: "组织", description: "叙述是否有层次，问题与结论能否被区分。", positiveWhen: "higher", evidenceLens: "查找拆解、顺序词和可追溯的理由。" },
  { key: "affect", label: "情绪语气", short: "语气", description: "文本中呈现的情绪稳定性与表达张力。", positiveWhen: "higher", evidenceLens: "只观察措辞强度与情绪词，不判断心理状态。" },
  { key: "pressure", label: "压力负荷", short: "压力", description: "任务拥挤、紧迫与反复受阻的语言信号。", positiveWhen: "lower", evidenceLens: "查找时间压力、堆叠任务和无解表述。" },
  { key: "action", label: "行动推进", short: "行动", description: "文本是否从意图走向具体、可执行的动作。", positiveWhen: "higher", evidenceLens: "查找动词、截止点、步骤和完成反馈。" },
  { key: "social", label: "社交取向", short: "协作", description: "对协作、沟通边界和他人反馈的表达方式。", positiveWhen: "higher", evidenceLens: "查找沟通对象、请求、承诺与边界。" },
]

const summaries = ["表达开始从愿望句转向带条件的判断，行动线索增加。", "任务较多，但文本仍能保持优先级和收尾动作。", "出现多线程切换，建议先减少并行问题的数量。", "沟通对象和边界写得更清楚，返工风险降低。", "压力词减少，行动表述稳定，适合复盘有效方法。"]
const evidence = ["先把今天的数据整理出来，再决定下一步。", "这个问题拆成两个部分处理，先完成可验证的一段。", "现在有点急，但我只处理最重要的一项。", "需要把判断依据写清楚，避免后面反复解释。", "今天的节奏更稳定，先把收尾做完。"]
const nextSteps = ["保留一个 25 分钟单任务区间。", "将未决问题压缩为一个可验证的问题。", "在收尾前写下明天的第一步。", "为高压力事项补一个明确截止点。", "复用今天有效的表达结构。"]

const bounded = (value: number) => Math.max(18, Math.min(92, value))
const demoDays: DemoDay[] = Array.from({ length: 30 }, (_, index) => {
  const day = new Date("2026-06-18T12:00:00")
  day.setDate(day.getDate() + index)
  const progress = index * 0.52
  return {
    date: day.toISOString().slice(0, 10),
    inputs: 14 + (index * 7) % 25,
    confidence: 0.74 + ((index * 3) % 14) / 100,
    summary: summaries[index % summaries.length],
    evidence: evidence[index % evidence.length],
    nextStep: nextSteps[index % nextSteps.length],
    scores: {
      clarity: bounded(55 + progress + Math.sin(index * 0.72) * 8),
      organization: bounded(52 + progress * 0.8 + Math.cos(index * 0.58) * 9),
      affect: bounded(57 + progress * 0.45 + Math.sin(index * 0.47 + 1) * 7),
      pressure: bounded(69 - progress * 0.82 + Math.cos(index * 0.61) * 9),
      action: bounded(47 + progress * 1.2 + Math.sin(index * 0.44 + 1) * 10),
      social: bounded(50 + progress * 0.5 + Math.cos(index * 0.38 + 2) * 8),
    },
  }
}).map(day => ({ ...day, scores: Object.fromEntries(Object.entries(day.scores).map(([key, value]) => [key, Math.round(value)])) as Record<MetricKey, number> }))

const mean = (values: number[]) => Math.round(values.reduce((total, value) => total + value, 0) / values.length)
const deviation = (values: number[]) => Math.round(Math.sqrt(values.reduce((total, value) => total + (value - mean(values)) ** 2, 0) / values.length))
const dateLabel = (value: string, withWeekday = false) => new Intl.DateTimeFormat("zh-CN", withWeekday ? { month: "long", day: "numeric", weekday: "short" } : { month: "numeric", day: "numeric" }).format(new Date(`${value}T12:00:00`))
const deltaLabel = (metric: typeof metrics[number], delta: number) => {
  const favorable = metric.positiveWhen === "higher" ? delta >= 0 : delta <= 0
  return { favorable, text: `${delta >= 0 ? "+" : ""}${delta} 分` }
}

function ScoreTone({ metric, value }: { metric: typeof metrics[number]; value: number }) {
  const normalized = metric.positiveWhen === "lower" ? 100 - value : value
  return <span className={normalized >= 72 ? "text-emerald-700" : normalized >= 50 ? "text-amber-700" : "text-rose-700"}>{value}</span>
}

export function MvpShowcase() {
  const [selectedIndex, setSelectedIndex] = useState(demoDays.length - 1)
  const [selectedMetric, setSelectedMetric] = useState<MetricKey>("clarity")
  const selected = demoDays[selectedIndex]
  const metric = metrics.find(item => item.key === selectedMetric) ?? metrics[0]
  const firstWeek = demoDays.slice(0, 7)
  const recentWeek = demoDays.slice(-7)
  const values = demoDays.map(day => day.scores[selectedMetric])
  const baseline = mean(firstWeek.map(day => day.scores[selectedMetric]))
  const recent = mean(recentWeek.map(day => day.scores[selectedMetric]))
  const delta = recent - baseline
  const chart = useMemo(() => {
    const width = 860
    const height = 250
    const top = 16
    const bottom = 32
    const plotHeight = height - top - bottom
    const point = (value: number, index: number) => ({ x: 14 + index * (width - 28) / (demoDays.length - 1), y: top + plotHeight - value / 100 * plotHeight })
    const rolling = values.map((_, index) => mean(values.slice(Math.max(0, index - 6), index + 1)))
    return { width, height, top, plotHeight, point, raw: values.map((value, index) => { const p = point(value, index); return `${p.x},${p.y}` }).join(" "), rolling: rolling.map((value, index) => { const p = point(value, index); return `${p.x},${p.y}` }).join(" ") }
  }, [values])
  const displayDelta = deltaLabel(metric, delta)

  return <div className="pb-10">
    <section className="border-b border-zinc-200 pb-8"><div className="flex flex-wrap items-center justify-between gap-4"><p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[.16em] text-emerald-700"><Sparkles size={15} />MVP demo dataset</p><span className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-600"><CalendarDays size={14} />2026.06.18 - 2026.07.17</span></div><div className="mt-6 grid gap-8 lg:grid-cols-[1.25fr_.75fr] lg:items-end"><div><h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">30 天的表达，<br />不是印象，是一组可核验的变化。</h1><p className="mt-5 max-w-2xl text-base leading-7 text-zinc-600">把每天清洗后的公开输入转为固定口径的六维观察。趋势、波动、文本证据和数据质量一起呈现，才能区分真正的持续变化与偶然的一天。</p></div><div className="border-l-2 border-emerald-700 pl-5"><p className="text-xs font-semibold uppercase tracking-[.14em] text-emerald-700">Executive readout</p><p className="mt-3 text-xl font-semibold leading-7">行动推进在近 7 日高于首周，压力负荷同步回落。</p><p className="mt-2 text-sm leading-6 text-zinc-600">这是演示集中的可观察信号，不是健康或人格判断。</p></div></div></section>

    <section className="grid gap-4 border-b border-zinc-200 py-7 sm:grid-cols-2 xl:grid-cols-4"><article className="border-t-2 border-zinc-950 pt-4"><p className="text-sm text-zinc-500">观察覆盖</p><p className="mt-2 text-3xl font-semibold">30 / 30</p><p className="mt-2 text-sm text-zinc-600">连续日期均有可用文本</p></article><article className="border-t-2 border-emerald-600 pt-4"><p className="text-sm text-zinc-500">有效输入</p><p className="mt-2 text-3xl font-semibold">{demoDays.reduce((total, day) => total + day.inputs, 0)} 段</p><p className="mt-2 text-sm text-zinc-600">平均 {mean(demoDays.map(day => day.inputs))} 段 / 日</p></article><article className="border-t-2 border-amber-500 pt-4"><p className="text-sm text-zinc-500">观察置信度</p><p className="mt-2 text-3xl font-semibold">{Math.round(mean(demoDays.map(day => day.confidence * 100)))}%</p><p className="mt-2 text-sm text-zinc-600">受输入量与证据完整度约束</p></article><article className="border-t-2 border-sky-600 pt-4"><p className="text-sm text-zinc-500">比较口径</p><p className="mt-2 text-3xl font-semibold">6 维</p><p className="mt-2 text-sm text-zinc-600">同一提示词、同一评分范围</p></article></section>

    <section className="py-8"><div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-emerald-700">Dimension panel</p><h2 className="mt-2 text-2xl font-semibold tracking-tight">先看完整结构，再下钻到一个信号。</h2><p className="mt-2 text-sm leading-6 text-zinc-600">近 7 日与首周的比较使用同一维度的日均分；波动度为 30 日标准差，帮助判断信号是否稳定。</p></div><p className="inline-flex items-center gap-2 text-xs text-zinc-500"><CircleAlert size={14} />分数只适合同一人的纵向比较</p></div><div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{metrics.map(item => { const recentScore = mean(recentWeek.map(day => day.scores[item.key])); const baselineScore = mean(firstWeek.map(day => day.scores[item.key])); const change = deltaLabel(item, recentScore - baselineScore); const active = item.key === selectedMetric; return <button key={item.key} onClick={() => setSelectedMetric(item.key)} className={`border p-4 text-left transition ${active ? "border-zinc-950 bg-zinc-950 text-white" : "border-zinc-200 bg-white hover:border-zinc-400"}`}><div className="flex items-start justify-between gap-4"><div><p className={`text-sm font-medium ${active ? "text-white" : "text-zinc-900"}`}>{item.label}</p><p className={`mt-1 text-xs leading-5 ${active ? "text-zinc-300" : "text-zinc-500"}`}>{item.description}</p></div><strong className={`text-2xl ${active ? "text-white" : ""}`}><ScoreTone metric={item} value={recentScore} /></strong></div><div className={`mt-4 flex items-center justify-between border-t pt-3 text-xs ${active ? "border-zinc-700 text-zinc-200" : "border-zinc-100 text-zinc-600"}`}><span>首周 {baselineScore} / 近 7 日 {recentScore}</span><span className={active ? "text-emerald-300" : change.favorable ? "text-emerald-700" : "text-rose-700"}>{change.text}</span></div></button> })}</div></section>

    <section className="border-y border-zinc-200 py-8"><div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-emerald-700">Thirty-day matrix</p><h2 className="mt-2 text-2xl font-semibold tracking-tight">30 × 6：不只看均值，也看变化发生在哪一天。</h2></div><div className="flex items-center gap-3 text-xs text-zinc-500"><span>低</span><span className="h-3 w-20 rounded-sm bg-gradient-to-r from-zinc-100 via-emerald-200 to-emerald-700" /><span>高</span></div></div><div className="mt-6 overflow-x-auto"><div className="min-w-[760px]"><div className="grid grid-cols-[5rem_repeat(30,minmax(0,1fr))] gap-1 text-[10px] text-zinc-400"> <span />{demoDays.map((day, index) => <span key={day.date} className="text-center">{index % 5 === 0 || index === 29 ? dateLabel(day.date) : ""}</span>)}</div><div className="mt-2 space-y-1">{metrics.map(item => <div key={item.key} className="grid grid-cols-[5rem_repeat(30,minmax(0,1fr))] gap-1"><span className="flex items-center text-xs font-medium text-zinc-600">{item.short}</span>{demoDays.map((day, index) => <button key={day.date} onClick={() => { setSelectedMetric(item.key); setSelectedIndex(index) }} title={`${dateLabel(day.date, true)} · ${item.label} ${day.scores[item.key]}`} aria-label={`查看 ${dateLabel(day.date, true)} ${item.label} ${day.scores[item.key]} 分`} className={`h-7 rounded-sm transition hover:ring-2 hover:ring-zinc-950 ${selectedIndex === index && selectedMetric === item.key ? "ring-2 ring-zinc-950" : ""}`} style={{ backgroundColor: `rgb(${232 - day.scores[item.key] * 1.3}, ${245 - day.scores[item.key] * 0.45}, ${236 - day.scores[item.key] * 1.1})` }} />)}</div>)}</div></div></div></section>

    <section className="grid gap-8 py-8 lg:grid-cols-[1.15fr_.85fr]"><div><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-emerald-700">Metric drill-down</p><h2 className="mt-2 text-2xl font-semibold tracking-tight">{metric.label}：最近 7 日 {recent} 分</h2></div><div className="text-right text-sm text-zinc-600"><p>首周 {baseline} 分</p><p className={`mt-1 inline-flex items-center gap-1 font-medium ${displayDelta.favorable ? "text-emerald-700" : "text-rose-700"}`}>{displayDelta.favorable ? <TrendingUp size={15} /> : <TrendingDown size={15} />}{displayDelta.text}</p></div></div><div className="mt-5 overflow-x-auto border-y border-zinc-200 py-4"><svg viewBox={`0 0 ${chart.width} ${chart.height}`} className="min-w-[680px] w-full" role="img" aria-label={`${metric.label} 30 日趋势图`}>{[25, 50, 75].map(value => <g key={value}><line x1="14" x2={chart.width - 14} y1={chart.top + chart.plotHeight - value / 100 * chart.plotHeight} y2={chart.top + chart.plotHeight - value / 100 * chart.plotHeight} stroke="#e4e4e7" /><text x={chart.width - 14} y={chart.top + chart.plotHeight - value / 100 * chart.plotHeight - 4} textAnchor="end" fill="#a1a1aa" fontSize="11">{value}</text></g>)}<polyline points={chart.raw} fill="none" stroke="#a1a1aa" strokeWidth="2" strokeLinecap="round" /><polyline points={chart.rolling} fill="none" stroke="#18181b" strokeWidth="3" strokeLinecap="round" />{demoDays.map((day, index) => { const point = chart.point(day.scores[selectedMetric], index); return <circle key={day.date} onClick={() => setSelectedIndex(index)} cx={point.x} cy={point.y} r={index === selectedIndex ? 5 : 3} fill={index === selectedIndex ? "#059669" : "white"} stroke="#18181b" strokeWidth="1.5" className="cursor-pointer" /> })}</svg></div><div className="mt-4 grid gap-3 sm:grid-cols-3"><div><p className="text-xs text-zinc-500">30 日均值</p><p className="mt-1 text-xl font-semibold">{mean(values)}</p></div><div><p className="text-xs text-zinc-500">30 日波动度</p><p className="mt-1 text-xl font-semibold">{deviation(values)} <span className="text-sm font-normal text-zinc-500">分</span></p></div><div><p className="text-xs text-zinc-500">观察视角</p><p className="mt-1 text-sm leading-5 text-zinc-700">{metric.evidenceLens}</p></div></div></div>
      <aside className="border border-zinc-200 bg-white p-5"><div className="flex items-center justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-emerald-700">Selected day</p><h2 className="mt-2 text-xl font-semibold">{dateLabel(selected.date, true)}</h2></div><button type="button" onClick={() => setSelectedIndex(index => Math.max(0, index - 1))} disabled={selectedIndex === 0} aria-label="查看前一天" className="rounded-md border border-zinc-200 p-2 text-zinc-700 disabled:opacity-30"><ChevronLeft size={16} /></button><button type="button" onClick={() => setSelectedIndex(index => Math.min(demoDays.length - 1, index + 1))} disabled={selectedIndex === demoDays.length - 1} aria-label="查看后一天" className="rounded-md border border-zinc-200 p-2 text-zinc-700 disabled:opacity-30"><ChevronRight size={16} /></button></div><p className="mt-5 text-sm leading-6 text-zinc-800">{selected.summary}</p><blockquote className="mt-5 border-l-2 border-zinc-300 pl-3 text-sm leading-6 text-zinc-600">“{selected.evidence}”</blockquote><div className="mt-5 grid grid-cols-2 gap-x-5 gap-y-3 border-y border-zinc-100 py-4">{metrics.map(item => <div key={item.key} className="flex items-center justify-between gap-3 text-xs"><span className="text-zinc-500">{item.short}</span><strong><ScoreTone metric={item} value={selected.scores[item.key]} /></strong></div>)}</div><div className="mt-5 flex items-start gap-3"><Target size={17} className="mt-0.5 shrink-0 text-emerald-700" /><div><p className="text-sm font-medium">建议的最小动作</p><p className="mt-1 text-sm leading-6 text-zinc-600">{selected.nextStep}</p></div></div><div className="mt-5 flex items-start gap-3 border-t border-zinc-100 pt-4"><Gauge size={17} className="mt-0.5 shrink-0 text-emerald-700" /><p className="text-xs leading-5 text-zinc-500">{selected.inputs} 段公开输入，观察置信度 {Math.round(selected.confidence * 100)}%。输入不足时，产品应降低断言强度，而非补全推测。</p></div></aside></section>

    <section className="grid gap-4 border-t border-zinc-200 py-8 lg:grid-cols-3"><article className="border border-zinc-200 bg-white p-5"><div className="flex items-center gap-2"><Activity size={17} className="text-emerald-700" /><h3 className="font-medium">可见的长期变化</h3></div><p className="mt-4 text-sm leading-6 text-zinc-700">本演示集里，行动推进与表达清晰的近 7 日均值都高于首周。产品只报告同一口径下的变化，不把分数解释为能力高低。</p></article><article className="border border-zinc-200 bg-white p-5"><div className="flex items-center gap-2"><Brain size={17} className="text-emerald-700" /><h3 className="font-medium">需要继续验证的信号</h3></div><p className="mt-4 text-sm leading-6 text-zinc-700">思路组织的波动仍然存在。下一步应在高波动日期回看证据，确认是场景变化、输入量变化，还是可重复的模式。</p></article><article className="border border-zinc-200 bg-white p-5"><div className="flex items-center gap-2"><MessageSquare size={17} className="text-emerald-700" /><h3 className="font-medium">面向使用者的价值</h3></div><p className="mt-4 text-sm leading-6 text-zinc-700">从“我最近感觉怎么样”变成“哪些表达信号在何时变化、依据是什么、我今天可尝试什么”。</p></article></section>

    <section className="flex gap-4 border-t border-zinc-200 pt-6 text-sm text-zinc-600"><LockKeyhole size={17} className="mt-0.5 shrink-0 text-emerald-700" /><p>本页为本地生成的演示数据。真实观察只基于用户主动允许的公开输入；每项结论都应保留模型版本、提示词版本、清洗版本、输入量和文本证据。该产品用于文本行为观察，不构成医疗、心理或人格诊断。</p></section>
  </div>
}
