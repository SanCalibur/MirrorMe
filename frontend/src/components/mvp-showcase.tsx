import { ArrowDownRight, ArrowUpRight, CalendarDays, LockKeyhole, Quote, Sparkles, Target } from "lucide-react"
import { useMemo, useState } from "react"

type DemoDay = {
  date: string
  clarity: number
  pressure: number
  action: number
  mood: number
  inputs: number
  summary: string
  evidence: string
  nextStep: string
}

const summaries = [
  "表达更聚焦，开始把模糊想法转成清晰的下一步。",
  "任务密度较高，但句子里仍保留了推进与取舍的线索。",
  "思路出现短暂分散，适合减少并行事项，先完成一个小闭环。",
  "沟通更直接，关键判断和边界表达得更清楚。",
  "压力信号回落，行动感稳定，适合整理本周的有效方法。",
]

const evidence = [
  "先把今天的数据整理出来，再决定下一步。",
  "这个问题我先拆成两个部分处理。",
  "现在有点急，但先完成最重要的一项。",
  "我需要把判断依据写清楚，避免后面反复解释。",
  "今天的节奏比前几天稳定一些。",
]

const nextSteps = ["保留一段 25 分钟的单任务时间。", "把未决问题压缩成一个可验证的问题。", "在收尾前写下明天的第一步。", "为高压力事项补一个明确的截止点。", "复用今天有效的表达结构。"]

const demoDays: DemoDay[] = Array.from({ length: 30 }, (_, index) => {
  const day = new Date("2026-06-18T12:00:00")
  day.setDate(day.getDate() + index)
  const lift = Math.round(index * 0.55)
  return {
    date: day.toISOString().slice(0, 10),
    clarity: 58 + lift + Math.round(Math.sin(index * 0.72) * 8),
    pressure: 67 - Math.round(index * 0.4) + Math.round(Math.cos(index * 0.6) * 9),
    action: 48 + lift + Math.round(Math.sin(index * 0.44 + 1) * 10),
    mood: 54 + Math.round(index * 0.35) + Math.round(Math.cos(index * 0.5) * 8),
    inputs: 14 + (index * 7) % 25,
    summary: summaries[index % summaries.length],
    evidence: evidence[index % evidence.length],
    nextStep: nextSteps[index % nextSteps.length],
  }
})

const formatDate = (value: string) => new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(new Date(`${value}T12:00:00`))
const compactDate = (value: string) => new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(new Date(`${value}T12:00:00`))
const average = (values: number[]) => Math.round(values.reduce((total, value) => total + value, 0) / values.length)

function Trend({ value, inverse = false }: { value: number; inverse?: boolean }) {
  const positive = inverse ? value < 0 : value > 0
  const Icon = positive ? ArrowUpRight : ArrowDownRight
  return <span className={`inline-flex items-center gap-1 text-xs font-medium ${positive ? "text-emerald-700" : "text-rose-700"}`}><Icon size={14} />{Math.abs(value)} 分</span>
}

export function MvpShowcase() {
  const [selectedIndex, setSelectedIndex] = useState(demoDays.length - 1)
  const selected = demoDays[selectedIndex]
  const recent = demoDays.slice(-7)
  const baseline = demoDays.slice(0, 7)
  const chart = useMemo(() => {
    const width = 920
    const height = 270
    const top = 18
    const bottom = 34
    const plotHeight = height - top - bottom
    const point = (value: number, index: number) => `${16 + index * (width - 32) / (demoDays.length - 1)},${top + plotHeight - value / 100 * plotHeight}`
    return { width, height, top, plotHeight, line: (key: "clarity" | "pressure" | "action") => demoDays.map((day, index) => point(day[key], index)).join(" "), point }
  }, [])

  return <div className="pb-8">
    <section className="border-b border-zinc-200 pb-8">
      <div className="flex flex-wrap items-center justify-between gap-4"><p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[.16em] text-emerald-700"><Sparkles size={15} />MVP demo dataset</p><span className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-600"><CalendarDays size={14} />2026.06.18 - 2026.07.17</span></div>
      <div className="mt-6 grid gap-8 lg:grid-cols-[1.3fr_.7fr] lg:items-end"><div><h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">30 天的表达，<br />能看见一个人正在怎样前进。</h1><p className="mt-5 max-w-2xl text-base leading-7 text-zinc-600">这不是给人贴标签，而是把零散输入沉淀为可回看的连续观察：什么时候更清楚，何时压力升高，哪些方式真正帮助你推进。</p></div><div className="border-l-2 border-emerald-700 pl-5"><p className="text-xs font-semibold uppercase tracking-[.14em] text-emerald-700">30-day signal</p><p className="mt-3 text-2xl font-semibold tracking-tight">表达清晰度 +18</p><p className="mt-2 text-sm leading-6 text-zinc-600">最近 7 天的压力负荷较首周下降 12 分，行动推进保持上升。</p></div></div>
    </section>

    <section className="grid gap-4 py-7 md:grid-cols-3"><article className="border-t-2 border-zinc-950 pt-4"><p className="text-sm text-zinc-500">连续观察</p><p className="mt-2 text-4xl font-semibold tracking-tight">30 <span className="text-lg font-medium text-zinc-500">天</span></p><p className="mt-2 text-sm text-zinc-600">每日一份可追溯的文本观察</p></article><article className="border-t-2 border-emerald-600 pt-4"><p className="text-sm text-zinc-500">有效输入</p><p className="mt-2 text-4xl font-semibold tracking-tight">{demoDays.reduce((total, day) => total + day.inputs, 0)} <span className="text-lg font-medium text-zinc-500">段</span></p><p className="mt-2 text-sm text-zinc-600">只以清洗后、用户允许的公开文本为依据</p></article><article className="border-t-2 border-amber-500 pt-4"><p className="text-sm text-zinc-500">可行动洞见</p><p className="mt-2 text-4xl font-semibold tracking-tight">6 <span className="text-lg font-medium text-zinc-500">项</span></p><p className="mt-2 text-sm text-zinc-600">从趋势变化转译为下一步建议</p></article></section>

    <section className="border-y border-zinc-200 py-7"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-emerald-700">Continuity over snapshots</p><h2 className="mt-2 text-2xl font-semibold tracking-tight">趋势不是分数的堆叠，是变化的方向。</h2></div><div className="flex flex-wrap gap-4 text-xs text-zinc-600"><span className="inline-flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-zinc-950" />表达清晰</span><span className="inline-flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-emerald-600" />行动推进</span><span className="inline-flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-amber-500" />压力负荷</span></div></div>
      <div className="mt-6 overflow-x-auto"><svg viewBox={`0 0 ${chart.width} ${chart.height}`} className="min-w-[700px] w-full" role="img" aria-label="30 日观察趋势图">{[25, 50, 75].map(value => <line key={value} x1="16" x2={chart.width - 16} y1={chart.top + chart.plotHeight - value / 100 * chart.plotHeight} y2={chart.top + chart.plotHeight - value / 100 * chart.plotHeight} stroke="#e4e4e7" />)}<polyline points={chart.line("clarity")} fill="none" stroke="#18181b" strokeWidth="3" strokeLinecap="round" /><polyline points={chart.line("action")} fill="none" stroke="#059669" strokeWidth="3" strokeLinecap="round" /><polyline points={chart.line("pressure")} fill="none" stroke="#d97706" strokeWidth="3" strokeLinecap="round" />{demoDays.map((day, index) => { const [x, y] = chart.point(day.clarity, index).split(","); return <g key={day.date} onClick={() => setSelectedIndex(index)} className="cursor-pointer"><circle cx={x} cy={y} r={index === selectedIndex ? 5 : 3} fill={index === selectedIndex ? "#18181b" : "white"} stroke="#18181b" strokeWidth="2" /><text x={x} y={chart.height - 10} textAnchor="middle" fill="#71717a" fontSize="11">{index % 5 === 0 || index === demoDays.length - 1 ? compactDate(day.date) : ""}</text></g>})}</svg></div>
      <div className="mt-4 grid grid-cols-10 gap-1 sm:grid-cols-15">{demoDays.map((day, index) => <button key={day.date} onClick={() => setSelectedIndex(index)} title={formatDate(day.date)} aria-label={`查看 ${formatDate(day.date)} 的观察`} className={`h-8 rounded-sm transition ${index === selectedIndex ? "bg-zinc-950" : "bg-emerald-100 hover:bg-emerald-300"}`} style={{ opacity: 0.35 + day.inputs / 55 }} />)}</div>
    </section>

    <section className="grid gap-8 py-8 lg:grid-cols-[1.2fr_.8fr]"><div><div className="flex items-center gap-2"><Quote size={18} className="text-emerald-700" /><h2 className="text-2xl font-semibold tracking-tight">{formatDate(selected.date)} 的观察</h2></div><p className="mt-5 max-w-2xl text-xl leading-8 text-zinc-800">{selected.summary}</p><blockquote className="mt-6 border-l-2 border-zinc-300 pl-4 text-sm leading-6 text-zinc-600">“{selected.evidence}”</blockquote><div className="mt-7 flex flex-wrap gap-2"><span className="rounded-full bg-zinc-100 px-3 py-1.5 text-xs text-zinc-600">{selected.inputs} 段公开输入</span><span className="rounded-full bg-zinc-100 px-3 py-1.5 text-xs text-zinc-600">置信度 82%</span><span className="rounded-full bg-zinc-100 px-3 py-1.5 text-xs text-zinc-600">可回看证据</span></div></div><aside className="border border-zinc-200 bg-white p-5"><div className="flex items-center gap-2"><Target size={17} className="text-emerald-700" /><h3 className="font-medium">把观察变成下一步</h3></div><p className="mt-4 text-lg font-medium leading-7">{selected.nextStep}</p><p className="mt-4 border-t border-zinc-100 pt-4 text-sm leading-6 text-zinc-600">产品不替你下结论。它把文本中的持续信号和依据摆出来，让你决定要保留、调整还是忽略什么。</p></aside></section>

    <section className="grid gap-4 border-t border-zinc-200 py-8 md:grid-cols-3"><article className="border border-zinc-200 bg-white p-5"><p className="text-sm font-medium">表达清晰度</p><p className="mt-3 text-3xl font-semibold">{average(recent.map(day => day.clarity))}</p><div className="mt-2"><Trend value={average(recent.map(day => day.clarity)) - average(baseline.map(day => day.clarity))} /></div><p className="mt-4 text-sm leading-6 text-zinc-600">更常出现明确的判断、边界和下一步，而不是只有模糊意图。</p></article><article className="border border-zinc-200 bg-white p-5"><p className="text-sm font-medium">压力负荷</p><p className="mt-3 text-3xl font-semibold">{average(recent.map(day => day.pressure))}</p><div className="mt-2"><Trend inverse value={average(recent.map(day => day.pressure)) - average(baseline.map(day => day.pressure))} /></div><p className="mt-4 text-sm leading-6 text-zinc-600">用趋势识别压力峰值出现的周期，而不是把某一天当作结论。</p></article><article className="border border-zinc-200 bg-white p-5"><p className="text-sm font-medium">行动推进</p><p className="mt-3 text-3xl font-semibold">{average(recent.map(day => day.action))}</p><div className="mt-2"><Trend value={average(recent.map(day => day.action)) - average(baseline.map(day => day.action))} /></div><p className="mt-4 text-sm leading-6 text-zinc-600">观察“说到做到”的语言线索是否变得更稳定、更可持续。</p></article></section>

    <section className="flex flex-col gap-4 border-t border-zinc-200 pt-6 text-sm text-zinc-600 sm:flex-row sm:items-start"><LockKeyhole size={17} className="mt-0.5 shrink-0 text-emerald-700" /><p>演示数据为本地生成的产品样本。真实使用时，观察仅基于用户主动允许的公开输入；LLM 配置与 API Key 不写入 SQLite。该产品用于文本行为观察，不构成医疗、心理或人格诊断。</p></section>
  </div>
}
