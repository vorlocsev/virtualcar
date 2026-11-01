#ifndef VC_NATIVE_FIXTURE_H
#define VC_NATIVE_FIXTURE_H
#include "../proxy/j2534_observer.h"
/* Synthetic DLL fixture only. Never connects to a driver, registry or vehicle. */
typedef struct {
    uint32_t calls[14], channel, a, b, c;
    const void *p, *q, *r, *s;
} vc_fixture_state;
enum { F_OPEN, F_CLOSE, F_CONNECT, F_DISCONNECT, F_READ, F_WRITE,
       F_START_PERIODIC, F_STOP_PERIODIC, F_START_FILTER, F_STOP_FILTER,
       F_VOLTAGE, F_VERSION, F_ERROR, F_IOCTL };
#endif
