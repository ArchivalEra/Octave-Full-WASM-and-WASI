#ifndef OCT_EMBED_H
#define OCT_EMBED_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*oct_stdout_cb)(const char *data, size_t len, void *user_data);

int oct_init(const char *octave_home);
void oct_shutdown(void);

int oct_eval(const char *code);
/* Caller must free the returned string with oct_free(). */
char *oct_eval_json(const char *expr);
void oct_free(char *ptr);

void oct_interrupt(void);
void oct_set_stdout_cb(oct_stdout_cb cb, void *user_data);

#ifdef __cplusplus
}
#endif

#endif /* OCT_EMBED_H */
