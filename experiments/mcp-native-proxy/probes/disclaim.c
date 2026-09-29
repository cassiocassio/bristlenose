#include <spawn.h>
#include <stdio.h>
#include <sys/wait.h>
extern char **environ;
int responsibility_spawnattrs_setdisclaim(posix_spawnattr_t *attrs, int disclaim);
int main(int c,char**v){posix_spawnattr_t a;posix_spawnattr_init(&a);
 int r=responsibility_spawnattrs_setdisclaim(&a,1);
 pid_t p;int e=posix_spawn(&p,v[1],NULL,&a,v+1,environ);
 if(e){printf("spawn failed %d (disclaim rc %d)\n",e,r);return 1;}
 int st;waitpid(p,&st,0);return WEXITSTATUS(st);}
