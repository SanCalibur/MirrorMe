import { BookOpenText, Save, Sparkles } from "lucide-react"
import { useEffect, useState } from "react"

type Diary = { date: string; content: string; source: string; updated_at: string }
const today = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai" }).format(new Date())

async function request<T>(url: string, init?: RequestInit) { const response = await fetch(url, init); if (!response.ok) throw new Error(await response.text()); return response.json() as Promise<T> }

export function DiaryWorkspace() {
  const [date, setDate] = useState(today())
  const [content, setContent] = useState("")
  const [status, setStatus] = useState("选择日期后读取日记。")
  const [running, setRunning] = useState(false)
  const load = async (value = date) => { const diary = await request<Diary | null>(`/api/diaries?date=${value}`); setContent(diary?.content ?? ""); setStatus(diary ? `上次保存于 ${diary.updated_at.slice(11, 16)}。` : "当天尚未生成日记。") }
  useEffect(() => { void load(date).catch(() => setStatus("无法读取当天日记。")) }, [date])
  const generate = async () => { setRunning(true); setStatus("正在根据已接受的清洗文本生成日记草稿..."); try { const diary = await request<Diary>("/api/diaries/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ date, api_url: sessionStorage.getItem("llm_url") || "", api_key: sessionStorage.getItem("llm_key") || "", model: sessionStorage.getItem("llm_model") || "", prompt: sessionStorage.getItem("llm_diary_prompt") || "" }) }); setContent(diary.content); setStatus("已生成草稿，可继续编辑后保存。") } catch (error) { setStatus(error instanceof Error ? `未生成日记：${error.message}` : "未生成日记。") } finally { setRunning(false) } }
  const save = async () => { try { const diary = await request<Diary>("/api/diaries", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ date, content }) }); setStatus(`已保存于 ${diary.updated_at.slice(11, 16)}。`) } catch (error) { setStatus(error instanceof Error ? `保存失败：${error.message}` : "保存失败。") } }
  return <><section className="border-b border-zinc-200 pb-8"><p className="text-xs font-semibold uppercase tracking-[.16em] text-emerald-700">Daily diary</p><div className="mt-3 flex flex-col justify-between gap-5 sm:flex-row sm:items-end"><div><h1 className="text-4xl font-semibold tracking-tight">把当天的片段，<br />写成可以回看的日记。</h1><p className="mt-4 max-w-xl text-sm leading-6 text-zinc-600">日记草稿只根据当天已接受的清洗文本生成；它保留不确定性，你可以随时改写并保存。</p></div><label className="text-sm text-zinc-600">日期<input type="date" value={date} onChange={event => setDate(event.target.value)} className="mt-2 block rounded-md border border-zinc-300 bg-white px-3 py-2" /></label></div></section><section className="grid gap-5 py-8 lg:grid-cols-[1fr_17rem]"><div><textarea value={content} onChange={event => setContent(event.target.value)} placeholder="生成草稿后在这里编辑，或直接开始书写。" className="min-h-[28rem] w-full resize-y rounded-lg border border-zinc-200 bg-white p-5 text-base leading-8 outline-none focus:border-emerald-600" /></div><aside className="border border-zinc-200 bg-white p-5"><BookOpenText className="text-emerald-700" /><h2 className="mt-4 font-medium">当天日记</h2><button disabled={running} onClick={() => void generate()} className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-950 px-3 py-3 text-sm text-white disabled:opacity-50"><Sparkles size={16} />{running ? "正在生成..." : "LLM 生成草稿"}</button><button onClick={() => void save()} className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-300 px-3 py-3 text-sm"><Save size={16} />保存日记</button><p className="mt-5 border-t border-zinc-100 pt-4 text-xs leading-5 text-zinc-500">{status}</p><p className="mt-4 text-xs leading-5 text-zinc-500">推荐使用本地 LLM。API Key 仅保存在当前浏览器会话。</p></aside></section></>
}
