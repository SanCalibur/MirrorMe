#include <cstdlib>
#include <cctype>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#ifdef MIRRORME_WITH_LIBRIME
#include <rime_api.h>
#endif

namespace {

std::string read_stdin() {
  std::ostringstream buffer;
  buffer << std::cin.rdbuf();
  return buffer.str();
}

std::string json_escape(const std::string& value) {
  std::string escaped;
  escaped.reserve(value.size());
  for (char ch : value) {
    switch (ch) {
      case '\\':
        escaped += "\\\\";
        break;
      case '"':
        escaped += "\\\"";
        break;
      case '\n':
        escaped += "\\n";
        break;
      case '\r':
        escaped += "\\r";
        break;
      case '\t':
        escaped += "\\t";
        break;
      default:
        escaped += ch;
        break;
    }
  }
  return escaped;
}

size_t key_colon_pos(const std::string& source, const std::string& key) {
  const std::string marker = "\"" + key + "\"";
  size_t search_from = 0;
  while (true) {
    const auto key_pos = source.find(marker, search_from);
    if (key_pos == std::string::npos) {
      return std::string::npos;
    }
    size_t cursor = key_pos + marker.size();
    while (cursor < source.size() && std::isspace(static_cast<unsigned char>(source[cursor]))) {
      ++cursor;
    }
    if (cursor < source.size() && source[cursor] == ':') {
      return cursor;
    }
    search_from = key_pos + marker.size();
  }
}

std::string string_field(const std::string& source, const std::string& key) {
  const auto colon_pos = key_colon_pos(source, key);
  if (colon_pos == std::string::npos) {
    return "";
  }
  const auto quote_pos = source.find('"', colon_pos + 1);
  if (quote_pos == std::string::npos) {
    return "";
  }
  std::string value;
  bool escaping = false;
  for (auto index = quote_pos + 1; index < source.size(); ++index) {
    const char ch = source[index];
    if (escaping) {
      value += ch;
      escaping = false;
      continue;
    }
    if (ch == '\\') {
      escaping = true;
      continue;
    }
    if (ch == '"') {
      break;
    }
    value += ch;
  }
  return value;
}

int int_field(const std::string& source, const std::string& key, int fallback) {
  const auto colon_pos = key_colon_pos(source, key);
  if (colon_pos == std::string::npos) {
    return fallback;
  }
  try {
    return std::stoi(source.substr(colon_pos + 1));
  } catch (...) {
    return fallback;
  }
}

const char* env_or_null(const char* name) {
  const char* value = std::getenv(name);
  return value && value[0] ? value : nullptr;
}

const char* env_or_fallback(const char* primary, const char* fallback) {
  const char* value = env_or_null(primary);
  return value ? value : env_or_null(fallback);
}

void print_error(const std::string& message) {
  std::cout << "{\"error\":\"" << json_escape(message) << "\"}" << std::endl;
}

void print_placeholder_result(const std::string& method, const std::string& text, const std::string& schema) {
  if (method == "schema") {
    std::cout
        << "{\"result\":{\"id\":\"" << json_escape(schema)
        << "\",\"name\":\"Rime schema placeholder\",\"engine\":\"librime-json-stdio-placeholder\","
        << "\"native\":false,\"sidecar_version\":\"" << MIRRORME_SIDECAR_VERSION << "\"}}"
        << std::endl;
    return;
  }

  if (method == "clear") {
    std::cout
        << "{\"result\":{\"schema\":\"" << json_escape(schema)
        << "\",\"input\":\"\",\"preedit\":\"\",\"candidates\":[],\"committed\":null}}"
        << std::endl;
    return;
  }

  const std::string committed = method == "commit" ? text : "";
  std::cout
      << "{\"result\":{\"schema\":\"" << json_escape(schema)
      << "\",\"input\":\"" << json_escape(text)
      << "\",\"preedit\":\"" << (method == "commit" ? "" : json_escape(text))
      << "\",\"candidates\":[{\"index\":1,\"text\":\"" << json_escape(text)
      << "\",\"annotation\":\"placeholder\",\"confidence\":0.1}],\"committed\":";
  if (method == "commit") {
    std::cout << "\"" << json_escape(committed) << "\"";
  } else {
    std::cout << "null";
  }
  std::cout << "}}" << std::endl;
}

#ifdef MIRRORME_WITH_LIBRIME
struct CandidatePayload {
  int index;
  std::string text;
  std::string annotation;
};

struct CompositionPayload {
  std::string schema;
  std::string input;
  std::string preedit;
  std::vector<CandidatePayload> candidates;
  std::string committed;
};

RimeTraits make_traits() {
  RIME_STRUCT(RimeTraits, traits);
  traits.app_name = "rime.mirrorme";
  traits.shared_data_dir = env_or_fallback("MIRRORME_RIME_SHARED_DATA_DIR", "MIRRORME_RIME_DATA_DIR");
  traits.user_data_dir = env_or_null("MIRRORME_RIME_USER_DATA_DIR");
  traits.prebuilt_data_dir = env_or_null("MIRRORME_RIME_PREBUILT_DATA_DIR");
  traits.staging_dir = env_or_null("MIRRORME_RIME_STAGING_DIR");
  traits.distribution_name = "MirrorMe";
  traits.distribution_code_name = "MirrorMe";
  traits.distribution_version = MIRRORME_SIDECAR_VERSION;
  return traits;
}

RimeApi* initialize_librime() {
  RimeApi* api = rime_get_api();
  RimeTraits traits = make_traits();
  api->setup(&traits);
  api->initialize(&traits);
  return api;
}

bool set_raw_input(RimeApi* api, RimeSessionId session, const std::string& text) {
  if (RIME_API_AVAILABLE(api, set_input)) {
    return api->set_input(session, text.c_str()) == True;
  }
  if (RIME_API_AVAILABLE(api, simulate_key_sequence)) {
    std::string compact;
    compact.reserve(text.size());
    for (char ch : text) {
      if (ch != ' ') {
        compact += ch;
      }
    }
    return api->simulate_key_sequence(session, compact.c_str()) == True;
  }
  for (char ch : text) {
    if (ch == ' ') {
      continue;
    }
    if (!api->process_key(session, static_cast<int>(ch), 0)) {
      return false;
    }
  }
  return true;
}

CompositionPayload read_context(
    RimeApi* api,
    RimeSessionId session,
    const std::string& schema,
    const std::string& input,
    const std::string& committed) {
  CompositionPayload payload;
  payload.schema = schema;
  payload.input = input;
  payload.committed = committed;

  RIME_STRUCT(RimeContext, context);
  if (!api->get_context(session, &context)) {
    return payload;
  }
  if (context.composition.preedit) {
    payload.preedit = context.composition.preedit;
  }
  for (int index = 0; index < context.menu.num_candidates; ++index) {
    const RimeCandidate& candidate = context.menu.candidates[index];
    payload.candidates.push_back(CandidatePayload{
        index + 1,
        candidate.text ? candidate.text : "",
        candidate.comment ? candidate.comment : "",
    });
  }
  api->free_context(&context);
  return payload;
}

std::string read_commit_text(RimeApi* api, RimeSessionId session) {
  RIME_STRUCT(RimeCommit, commit);
  if (!api->get_commit(session, &commit)) {
    return "";
  }
  std::string text = commit.text ? commit.text : "";
  api->free_commit(&commit);
  return text;
}

void print_composition_result(const CompositionPayload& payload) {
  std::cout
      << "{\"result\":{\"schema\":\"" << json_escape(payload.schema)
      << "\",\"input\":\"" << json_escape(payload.input)
      << "\",\"preedit\":\"" << json_escape(payload.preedit)
      << "\",\"candidates\":[";
  for (size_t index = 0; index < payload.candidates.size(); ++index) {
    const CandidatePayload& candidate = payload.candidates[index];
    if (index > 0) {
      std::cout << ",";
    }
    std::cout
        << "{\"index\":" << candidate.index
        << ",\"text\":\"" << json_escape(candidate.text)
        << "\",\"annotation\":\"" << json_escape(candidate.annotation)
        << "\",\"confidence\":0.5}";
  }
  std::cout << "],\"committed\":";
  if (payload.committed.empty()) {
    std::cout << "null";
  } else {
    std::cout << "\"" << json_escape(payload.committed) << "\"";
  }
  std::cout << "}}" << std::endl;
}

void print_schema_result(RimeApi* api, RimeSessionId session, const std::string& fallback_schema) {
  RIME_STRUCT(RimeStatus, status);
  std::string schema_id = fallback_schema;
  std::string schema_name = fallback_schema;
  if (api->get_status(session, &status)) {
    if (status.schema_id) {
      schema_id = status.schema_id;
    }
    if (status.schema_name) {
      schema_name = status.schema_name;
    }
    api->free_status(&status);
  }
  const char* version = RIME_API_AVAILABLE(api, get_version) ? api->get_version() : "";
  std::cout
      << "{\"result\":{\"id\":\"" << json_escape(schema_id)
      << "\",\"name\":\"" << json_escape(schema_name)
      << "\",\"engine\":\"librime\",\"native\":true,\"librime_version\":\""
      << json_escape(version ? version : "")
      << "\",\"sidecar_version\":\"" << MIRRORME_SIDECAR_VERSION << "\"}}"
      << std::endl;
}

int run_librime_request(
    const std::string& method,
    const std::string& text,
    const std::string& schema,
    int candidate_index) {
  RimeApi* api = initialize_librime();
  RimeSessionId session = api->create_session();
  if (!session) {
    print_error("Failed to create librime session.");
    api->finalize();
    return 1;
  }

  if (!api->select_schema(session, schema.c_str())) {
    api->destroy_session(session);
    api->finalize();
    print_error("Failed to select Rime schema: " + schema);
    return 1;
  }

  if (method == "schema") {
    print_schema_result(api, session, schema);
    api->destroy_session(session);
    api->finalize();
    return 0;
  }

  if (method == "clear") {
    api->clear_composition(session);
    CompositionPayload payload;
    payload.schema = schema;
    print_composition_result(payload);
    api->destroy_session(session);
    api->finalize();
    return 0;
  }

  if (!set_raw_input(api, session, text)) {
    api->destroy_session(session);
    api->finalize();
    print_error("Failed to set Rime input.");
    return 1;
  }

  std::string committed;
  if (method == "commit") {
    const size_t zero_based_index = candidate_index > 0 ? static_cast<size_t>(candidate_index - 1) : 0;
    if (!api->select_candidate(session, zero_based_index)) {
      api->commit_composition(session);
    }
    committed = read_commit_text(api, session);
    if (committed.empty()) {
      api->destroy_session(session);
      api->finalize();
      print_error("Rime did not produce committed text.");
      return 1;
    }
  }

  CompositionPayload payload = read_context(api, session, schema, text, committed);
  if (method == "commit") {
    payload.preedit.clear();
    payload.committed = committed;
  }
  print_composition_result(payload);

  api->destroy_session(session);
  api->finalize();
  return 0;
}
#endif

}  // namespace

int main() {
  const std::string request = read_stdin();
  if (request.empty()) {
    print_error("Empty JSON-stdio request.");
    return 1;
  }

  const std::string method = string_field(request, "method");
  const std::string text = string_field(request, "text");
  std::string schema = string_field(request, "schema");
  if (schema.empty()) {
    schema = "luna_pinyin";
  }

  if (method.empty()) {
    print_error("Missing method.");
    return 1;
  }

  if (method != "schema" && method != "compose" && method != "candidates" &&
      method != "commit" && method != "clear") {
    print_error("Unsupported method: " + method);
    return 1;
  }

  const int candidate_index = int_field(request, "candidate_index", 1);

#ifdef MIRRORME_WITH_LIBRIME
  return run_librime_request(method, text, schema, candidate_index);
#endif

  print_placeholder_result(method, text, schema);
  return 0;
}
