/* CRT-free stand-ins required by compiler-generated aggregate copies.
 * Do not import MSVCRT into the x86 J2534 wrapper. */
#include <stddef.h>
void *memset(void *dst,int value,size_t n) {
    volatile unsigned char *p=(volatile unsigned char *)dst;
    size_t i;
    for(i=0;i<n;i++)p[i]=(unsigned char)value;
    return dst;
}
void *memcpy(void *dst,const void *src,size_t n) {
    volatile unsigned char *p=(volatile unsigned char *)dst;
    const volatile unsigned char *s=(const volatile unsigned char *)src;
    size_t i;
    for(i=0;i<n;i++)p[i]=s[i];
    return dst;
}
