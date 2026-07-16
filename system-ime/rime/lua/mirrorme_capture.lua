local function json_escape(value)
  value = value:gsub("\\", "\\\\")
  value = value:gsub('"', '\\"')
  value = value:gsub("\b", "\\b")
  value = value:gsub("\f", "\\f")
  value = value:gsub("\n", "\\n")
  value = value:gsub("\r", "\\r")
  value = value:gsub("\t", "\\t")
  return value
end

local function processor(_, _)
  return 2
end

local function append_commit(queue_path, text)
  if not text or text == "" then
    return
  end
  local queue = io.open(queue_path, "a")
  if not queue then
    return
  end
  queue:write('{"version":1,"text":"' .. json_escape(text) .. '"}\n')
  queue:close()
end

local function init(env)
  local queue_path = rime_api:get_user_data_dir() .. "/mirrorme-ime-commits.ndjson"
  env.notifier = env.engine.context.commit_notifier:connect(function(context)
    append_commit(queue_path, context:get_commit_text())
  end)
end

return { init = init, func = processor }
