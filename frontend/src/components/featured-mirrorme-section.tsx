import { BrainCircuit, FileText, PenLine, Sparkles } from "lucide-react"
import { useEffect, useState } from "react"
import { Card, CardContent } from "./ui/card"

type Overview = { date: string; events: { total: number }; summary: { summary: string; topics: string[] } }
const actions = [
  { icon: PenLine, title: "记录输出", detail: "快速写下正在发生的想法与决定。" },
  { icon: FileText, title: "当日摘要", detail: "从今天的表达中看见主线。" },
  { icon: BrainCircuit, title: "状态观察", detail: "留存每日连续的状态线索。" },
  { icon: Sparkles, title: "文本清洗", detail: "用本地规则或 LLM 精炼文本。" },
]
export default function FeaturedMirrorMeSection() {
  const [data, setData] = useState<Overview | null>(null)
  const [text, setText] = useState("")
  const [message, setMessage] = useState("读取本地数据中")
  const date = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai" }).format(new Date())
  const load = async () => { const response = await fetch(`/api/daily?date=${date}`); const next = await response.json() as Overview; setData(next); setMessage("本地数据已更新") }
  useEffect(() => { void load() }, [])
  const capture = async () => { if (!text.trim()) return; await fetch("/api/events", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) }); setText(""); await load(); setMessage("记录已写入本地 SQLite") }
  return <main className="mx-auto min-h-screen max-w-7xl bg-white px-6 pb-16 text-zinc-950 sm:px-10"><header className="flex items-center justify-between py-6"><a href="/" className="font-semibold">MirrorMe</a><div className="flex gap-4 text-sm"><a href="/state">状态观察</a><button onClick={() => void load()} className="rounded-lg border border-zinc-200 px-3 py-2">刷新</button></div></header><section className="border-b border-zinc-200 py-12"><p className="text-xs font-semibold uppercase tracking-[.15em] text-emerald-700">Personal output system</p><h1 className="mt-3 text-5xl font-semibold tracking-tight sm:text-6xl">把每天的表达，<br />留成可读的自己。</h1></section><section className="mt-5 grid grid-cols-1 gap-2 lg:grid-cols-3"><Card className="min-h-[500px] border-0 bg-zinc-950 text-white lg:col-span-2"><CardContent className="flex h-full min-h-[500px] flex-col justify-between p-8"><div className="flex justify-between text-sm text-zinc-400"><span>{data?.date ?? date}</span><span>{data?.events.total ?? 0} 条输出</span></div><p className="max-w-2xl text-2xl leading-relaxed sm:text-3xl">{data?.summary.summary || "今天还没有公开输出。先写下一句值得留下的话。"}</p><div className="flex flex-wrap gap-2">{(data?.summary.topics || ["等待主题"]).slice(0, 5).map((topic) => <span key={topic} className="rounded-full border border-zinc-700 px-3 py-1 text-xs text-zinc-300">{topic}</span>)}</div></CardContent></Card><div className="grid grid-cols-2 gap-2">{actions.map(({ icon: Icon, title, detail }) => <Card key={title} className="min-h-[244px] transition hover:shadow-lg"><CardContent className="flex h-full flex-col justify-between"><Icon size={20} /><div><h2 className="text-sm font-medium">{title}</h2><p className="mt-2 text-xs leading-relaxed text-zinc-500">{detail}</p></div></CardContent></Card>)}</div></section><section className="mt-5 grid gap-3 border border-zinc-200 bg-zinc-50 p-5 md:grid-cols-[1fr_auto]"><textarea value={text} onChange={(event) => setText(event.target.value)} rows={4} placeholder="写下一段输出" className="w-full resize-none rounded-lg border border-zinc-200 bg-white p-3 outline-none" /><button onClick={() => void capture()} className="self-end rounded-lg bg-zinc-950 px-5 py-3 text-sm font-medium text-white">保存记录</button></section><footer className="py-6 text-xs text-zinc-500">{message}</footer></main>
}
