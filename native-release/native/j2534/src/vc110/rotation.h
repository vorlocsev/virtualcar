#ifndef VC110_ROTATION_H
#define VC110_ROTATION_H
#include <stdint.h>
#define VC110_LIMIT (32u*1024u*1024u)
#define VC110_ARCHIVES 3u
/* Caller holds a cross-process lock for the entire transaction. Slot 0 active.
   size: 1 exists, 0 absent, -1 error. move: 1 moved/absent, 0 error.
   append must perform one write and report full success. */
typedef struct {
    int (*size)(void *, unsigned, uint64_t *);
    int (*move)(void *, unsigned, unsigned);
    int (*append)(void *, const char *, unsigned);
} vc110_ops;
static inline int vc110_record(const vc110_ops *ops, void *ctx, uint64_t cap,
                               const char *line, unsigned length) {
    uint64_t size=0; int present; unsigned i;
    if (!ops || !ops->size || !ops->move || !ops->append || !line || !length || length>cap) return 0;
    present=ops->size(ctx,0,&size);
    if (present<0) return 0;
    if (!present) size=0;
    if (size>cap-length) {
        for (i=VC110_ARCHIVES;i>0;--i) if (!ops->move(ctx,i-1,i)) return 0;
    }
    return ops->append(ctx,line,length);
}
void vc110_write(const char *path, const char *line, unsigned length);
#endif
