#include "oct_embed.h"

#include <cstdlib>
#include <cstring>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>

#include <octave/oct.h>
#include <octave/interpreter.h>
#include <octave/parse.h>
#include <octave/quit.h>

namespace {
std::unique_ptr<octave::interpreter> g_interp;
oct_stdout_cb g_stdout_cb = nullptr;
void *g_stdout_ud = nullptr;

class callback_streambuf : public std::streambuf {
public:
  int overflow(int c) override {
    if (c != EOF) {
      char ch = static_cast<char>(c);
      if (g_stdout_cb) {
        g_stdout_cb(&ch, 1, g_stdout_ud);
      }
    }
    return c;
  }

  std::streamsize xsputn(const char *s, std::streamsize n) override {
    if (g_stdout_cb && n > 0) {
      g_stdout_cb(s, static_cast<size_t>(n), g_stdout_ud);
    }
    return n;
  }
};

callback_streambuf g_cb_buf;
std::streambuf *g_orig_cout = nullptr;
} // namespace

extern "C" {

int oct_init(const char *octave_home) {
  if (g_interp) {
    return 0;
  }
  if (octave_home && *octave_home) {
    setenv("OCTAVE_HOME", octave_home, 1);
  }
  try {
    g_interp = std::make_unique<octave::interpreter>();
    g_interp->initialize_history(false);
    g_interp->initialize_load_path(true);
    int status = g_interp->execute();
    (void)status;
    g_orig_cout = std::cout.rdbuf(&g_cb_buf);
    return 0;
  } catch (...) {
    g_interp.reset();
    return -1;
  }
}

void oct_shutdown(void) {
  if (g_orig_cout) {
    std::cout.rdbuf(g_orig_cout);
    g_orig_cout = nullptr;
  }
  g_interp.reset();
}

int oct_eval(const char *code) {
  if (!g_interp || !code) {
    return -1;
  }
  try {
    int parse_status = 0;
    g_interp->eval_string(std::string(code), false, parse_status, 0);
    return parse_status;
  } catch (const octave::execution_exception &) {
    return -2;
  } catch (...) {
    return -3;
  }
}

char *oct_eval_json(const char *expr) {
  if (!g_interp || !expr) {
    return nullptr;
  }
  try {
    int parse_status = 0;
    octave_value_list out =
        g_interp->eval_string(std::string(expr), true, parse_status, 1);
    if (parse_status != 0 || out.empty()) {
      const char *err = "{\"ok\":false,\"error\":\"eval_failed\"}";
      return strdup(err);
    }
    octave_value_list json_out = octave::feval("jsonencode", out(0), 1);
    std::string s = json_out(0).string_value();
    return strdup(s.c_str());
  } catch (...) {
    const char *err = "{\"ok\":false,\"error\":\"exception\"}";
    return strdup(err);
  }
}

void oct_free(char *ptr) { std::free(ptr); }

void oct_interrupt(void) { octave_interrupt_state = 1; }

void oct_set_stdout_cb(oct_stdout_cb cb, void *user_data) {
  g_stdout_cb = cb;
  g_stdout_ud = user_data;
}

} // extern "C"
