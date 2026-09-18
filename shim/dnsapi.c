/*
 * dnsapi.dll shim for running Formlabs PreFormServer under Wine older than 11.13.
 *
 * PreFormServer.exe imports DnsStartMulticastQuery and DnsStopMulticastQuery
 * (mDNS printer discovery). Wine releases before 11.13 export neither, and
 * Wine aborts a process the moment it calls an unimplemented function, so
 * PreFormServer died right after "starting HTTP server". Wine 11.13 added
 * both as stubs that return ERROR_SUCCESS (commits c13fd5de90 and 11bca8ddea);
 * this DLL does exactly the same thing for older Wine.
 *
 * Because a native DLL replaces Wine's builtin dnsapi for the whole process,
 * it must also export what Qt6Network.dll imports: DnsQueryEx,
 * DnsWriteQuestionToBuffer_W, DnsExtractRecordsFromMessage_W and DnsFree.
 * Those back QDnsLookup, which PreFormServer does not use; they report
 * "not implemented" instead of resolving anything. Ordinary host-name lookups
 * go through ws2_32 getaddrinfo and are unaffected.
 *
 * Load it with WINEDLLOVERRIDES="dnsapi=n" from PreFormServer's directory.
 * Build: make (needs x86_64-w64-mingw32-gcc).
 */
#include <windows.h>

typedef LONG DNS_STATUS;

#ifndef DNS_ERROR_RCODE_NOT_IMPLEMENTED
#define DNS_ERROR_RCODE_NOT_IMPLEMENTED 9004L
#endif

/* --- what PreFormServer.exe imports --------------------------------------- */

DNS_STATUS WINAPI DnsStartMulticastQuery(void *request, void *handle)
{
    (void)request;
    (void)handle;
    /* Report success and never deliver a result: no mDNS answers ever arrive. */
    return ERROR_SUCCESS;
}

DNS_STATUS WINAPI DnsStopMulticastQuery(void *handle)
{
    (void)handle;
    return ERROR_SUCCESS;
}

VOID WINAPI DnsFree(PVOID data, int free_type)
{
    /* Nothing in this DLL allocates, so there is never anything to free. */
    (void)data;
    (void)free_type;
}

/* --- what Qt6Network.dll imports (QDnsLookup; unused by PreFormServer) ---- */

DNS_STATUS WINAPI DnsQueryEx(void *request, void *result, void *cancel)
{
    (void)request;
    (void)result;
    (void)cancel;
    return DNS_ERROR_RCODE_NOT_IMPLEMENTED;
}

BOOL WINAPI DnsWriteQuestionToBuffer_W(void *buffer, DWORD *size, const WCHAR *name, WORD type, WORD xid, BOOL recursion)
{
    (void)buffer;
    (void)size;
    (void)name;
    (void)type;
    (void)xid;
    (void)recursion;
    SetLastError(ERROR_CALL_NOT_IMPLEMENTED);
    return FALSE;
}

DNS_STATUS WINAPI DnsExtractRecordsFromMessage_W(void *message, WORD length, void **records)
{
    (void)message;
    (void)length;
    if (records) *records = NULL;
    return DNS_ERROR_RCODE_NOT_IMPLEMENTED;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) DisableThreadLibraryCalls(instance);
    return TRUE;
}
