#define _GNU_SOURCE
#include <errno.h>
#include <unistd.h>
#include <string.h>
#include <sys/syscall.h>
/* LibreOffice 7.3 ignores its socket-path hint whenever access(/tmp,W_OK)
 * succeeds. Landlock intentionally does not affect access(2). Prefer the
 * private OSL_SOCKET_PATH without granting writes to the shared /tmp. */
int access(const char *path, int mode) {
    if ((mode & W_OK) && (!strcmp(path,"/tmp") || !strcmp(path,"/var/tmp"))) {
        errno = EACCES;
        return -1;
    }
    return syscall(SYS_access,path,mode);
}
