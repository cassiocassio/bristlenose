#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
extern int responsibility_get_pid_responsible_for_pid(pid_t);
int main(int argc, char **argv) {
  const char *out = getenv("PROBE_OUT");
  FILE *o = out ? fopen(out, "a") : stdout; if (!o) o = stdout;
  pid_t r = responsibility_get_pid_responsible_for_pid(getpid());
  fprintf(o, "pid=%d ppid=%d responsible=%d\n", getpid(), getppid(), r);
  for (int i = 1; i < argc; i++) {
    const char *p = argv[i];
    if (strncmp(p, "W:", 2) == 0) {
      p += 2; int fd = open(p, O_WRONLY|O_CREAT|O_TRUNC, 0600);
      if (fd < 0) { fprintf(o, "WRITE %s -> errno %d %s\n", p, errno, strerror(errno)); continue; }
      write(fd, "probe\n", 6); close(fd); fprintf(o, "WRITE %s -> ok\n", p);
    } else if (strncmp(p, "D:", 2) == 0) {
      p += 2; DIR *d = opendir(p);
      if (!d) { fprintf(o, "LIST %s -> errno %d %s\n", p, errno, strerror(errno)); continue; }
      int n = 0; while (readdir(d)) n++; closedir(d); fprintf(o, "LIST %s -> ok (%d entries)\n", p, n);
    } else if (strncmp(p, "U:", 2) == 0) {
      p += 2; fprintf(o, "UNLINK %s -> %s\n", p, unlink(p) == 0 ? "ok" : strerror(errno));
    } else {
      int fd = open(p, O_RDONLY);
      if (fd < 0) { fprintf(o, "READ %s -> errno %d %s\n", p, errno, strerror(errno)); continue; }
      char buf[64]; ssize_t n = read(fd, buf, sizeof buf); close(fd);
      fprintf(o, "READ %s -> ok (%zd bytes)\n", p, n);
    }
  }
  if (o != stdout) fclose(o);
  return 0;
}
