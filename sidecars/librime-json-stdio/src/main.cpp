#include <iostream>
#include <sstream>
#include <string>

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

std::string string_field(const std::string& source, const std::string& key) {
  const std::string marker = "\"" + key + "\"";
  const auto key_pos = source.find(marker);
  if (key_pos == std::string::npos) {
    return "";
  }
  const auto colon_pos = source.find(':', key_pos + marker.size());
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
  const std::string marker = "\"" + key + "\"";
  const auto key_pos = source.find(marker);
  if (key_pos == std::string::npos) {
    return fallback;
  }
  const auto colon_pos = source.find(':', key_pos + marker.size());
  if (colon_pos == std::string::npos) {
    return fallback;
  }
  try {
    return std::stoi(source.substr(colon_pos + 1));
  } catch (...) {
    return fallback;
  }
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
void initialize_librime() {
  RimeApi* api = rime_get_api();
  RIME_STRUCT(RimeTraits, traits);
  traits.app_name = "rime.mirrorme";
  api->setup(&traits);
  api->initialize(&traits);
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

  (void)int_field(request, "candidate_index", 1);

#ifdef MIRRORME_WITH_LIBRIME
  // TODO: Replace the placeholder below with real session logic:
  // 1. initialize_librime()
  // 2. create_session()
  // 3. select_schema(schema)
  // 4. process_key()/simulate_key_sequence() from input text
  // 5. get_context()/candidate_list_* for candidates
  // 6. select_candidate()/get_commit() for commit
  // 7. free_context()/free_commit()/destroy_session()/finalize()
  initialize_librime();
#endif

  print_placeholder_result(method, text, schema);
  return 0;
}
