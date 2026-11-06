#ifndef DVINHOLM_DIAGNOSTIC_CORE_H
#define DVINHOLM_DIAGNOSTIC_CORE_H

#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Stable C ABI v1. Each returned handle must be closed exactly once.
 * Read-only opens never create or alter the SQLite database.
 * Paths are NUL-terminated UTF-8, not UTF-16.
 * Never pass an arbitrary/freed handle or share it concurrently across threads.
 */
typedef struct dc_db dc_db;
enum {
    DC_OK = 0,
    DC_ERR_ARGUMENT = 1,
    DC_ERR_OPEN = 2,
    DC_ERR_QUERY = 3
};
uint32_t dc_abi_version(void);
uint32_t dc_schema_version(void);
int32_t dc_db_open_readonly(const char *utf8_path, dc_db **out_handle);
int32_t dc_db_source_count(dc_db *handle, uint64_t *out_count);
void dc_db_close(dc_db *handle);

#ifdef __cplusplus
}
#endif
#endif
