// cat(1) for one file, to be team-signed and run disclaimed: reads Bristlenose's
// data container as a same-team process and writes the bytes to stdout. Spike
// harness for seeding the app-group handshake (see ../README.md).
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>
int main(int argc, char **argv) {
    if (argc < 2) return 64;
    int fd = open(argv[1], O_RDONLY);
    if (fd < 0) { perror("teamcat"); return 1; }
    char buf[8192]; ssize_t n;
    while ((n = read(fd, buf, sizeof buf)) > 0) write(1, buf, (size_t)n);
    close(fd);
    return 0;
}
