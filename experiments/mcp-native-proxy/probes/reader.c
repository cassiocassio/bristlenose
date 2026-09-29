#include <stdio.h>
#include <errno.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
int main(int c,char**v){int fd=open(v[1],O_RDONLY);if(fd<0){printf("%s: DENIED errno=%d %s\n",v[2],errno,strerror(errno));return 1;}char b[16];ssize_t n=read(fd,b,sizeof b);printf("%s: READ ok (%zd bytes)\n",v[2],n);return 0;}
