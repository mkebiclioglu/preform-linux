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
 * it must also export what everything else in the process imports from it:
 *  - Qt6Network.dll: DnsQueryEx, DnsWriteQuestionToBuffer_W,
 *    DnsExtractRecordsFromMessage_W, DnsFree (QDnsLookup, unused by
 *    PreFormServer; they report "not implemented").
 *  - Wine's own iphlpapi.dll: DnsQueryConfig (GetAdaptersAddresses,
 *    GetNetworkParams). Implemented for real for the host-name variants and
 *    as "no DNS servers, no search list" otherwise.
 *  - Wine's ws2_32.dll and netapi32.dll: DnsQuery_A/W, DnsRecordListFree
 *    (fail cleanly; ordinary name resolution uses getaddrinfo, not these).
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

/* --- what Wine's iphlpapi, ws2_32 and netapi32 import ----------------------- */

/* DNS_CONFIG_TYPE values from windns.h */
#define CFG_PRIMARY_DOMAIN_W 0
#define CFG_PRIMARY_DOMAIN_A 1
#define CFG_PRIMARY_DOMAIN_UTF8 2
#define CFG_DNS_SERVER_LIST 6
#define CFG_SEARCH_LIST 7
#define CFG_HOST_NAME_W 12
#define CFG_HOST_NAME_A 13
#define CFG_HOST_NAME_UTF8 14
#define CFG_FULL_HOST_NAME_W 15
#define CFG_FULL_HOST_NAME_A 16
#define CFG_FULL_HOST_NAME_UTF8 17

static DNS_STATUS name_w(COMPUTER_NAME_FORMAT fmt, void *buffer, DWORD *len)
{
    DWORD chars = 0;
    GetComputerNameExW(fmt, NULL, &chars); /* fails with ERROR_MORE_DATA, sets chars incl. NUL */
    if (chars == 0) chars = 1;
    if (!buffer || *len < chars * sizeof(WCHAR))
    {
        *len = chars * sizeof(WCHAR);
        return ERROR_MORE_DATA;
    }
    chars = *len / sizeof(WCHAR);
    if (!GetComputerNameExW(fmt, (WCHAR *)buffer, &chars))
    {
        ((WCHAR *)buffer)[0] = 0;
        chars = 0;
    }
    *len = (chars + 1) * sizeof(WCHAR);
    return ERROR_SUCCESS;
}

static DNS_STATUS name_a(COMPUTER_NAME_FORMAT fmt, void *buffer, DWORD *len)
{
    DWORD chars = 0;
    GetComputerNameExA(fmt, NULL, &chars);
    if (chars == 0) chars = 1;
    if (!buffer || *len < chars)
    {
        *len = chars;
        return ERROR_MORE_DATA;
    }
    chars = *len;
    if (!GetComputerNameExA(fmt, (char *)buffer, &chars))
    {
        ((char *)buffer)[0] = 0;
        chars = 0;
    }
    *len = chars + 1;
    return ERROR_SUCCESS;
}

DNS_STATUS WINAPI DnsQueryConfig(int config, DWORD flag, const WCHAR *adapter, void *reserved, void *buffer, DWORD *len)
{
    (void)flag;
    (void)adapter;
    (void)reserved;
    if (!len) return ERROR_INVALID_PARAMETER;
    switch (config)
    {
    case CFG_DNS_SERVER_LIST:
        /* An IP4_ARRAY with AddrCount == 0: iphlpapi then reports no DNS servers. */
        if (!buffer || *len < sizeof(DWORD))
        {
            *len = sizeof(DWORD);
            return ERROR_MORE_DATA;
        }
        *(DWORD *)buffer = 0;
        *len = sizeof(DWORD);
        return ERROR_SUCCESS;
    case CFG_SEARCH_LIST:
    case CFG_PRIMARY_DOMAIN_W:
    case CFG_PRIMARY_DOMAIN_A:
    case CFG_PRIMARY_DOMAIN_UTF8:
        return ERROR_NO_DATA;
    case CFG_HOST_NAME_W:
        return name_w(ComputerNameDnsHostname, buffer, len);
    case CFG_HOST_NAME_A:
    case CFG_HOST_NAME_UTF8:
        return name_a(ComputerNameDnsHostname, buffer, len);
    case CFG_FULL_HOST_NAME_W:
        return name_w(ComputerNameDnsFullyQualified, buffer, len);
    case CFG_FULL_HOST_NAME_A:
    case CFG_FULL_HOST_NAME_UTF8:
        return name_a(ComputerNameDnsFullyQualified, buffer, len);
    default:
        return ERROR_INVALID_PARAMETER;
    }
}

#ifndef DNS_ERROR_RCODE_SERVER_FAILURE
#define DNS_ERROR_RCODE_SERVER_FAILURE 9002L
#endif

DNS_STATUS WINAPI DnsQuery_A(const char *name, WORD type, DWORD options, void *extra, void **results, void **reserved)
{
    (void)name;
    (void)type;
    (void)options;
    (void)extra;
    (void)reserved;
    if (results) *results = NULL;
    return DNS_ERROR_RCODE_SERVER_FAILURE;
}

DNS_STATUS WINAPI DnsQuery_W(const WCHAR *name, WORD type, DWORD options, void *extra, void **results, void **reserved)
{
    (void)name;
    (void)type;
    (void)options;
    (void)extra;
    (void)reserved;
    if (results) *results = NULL;
    return DNS_ERROR_RCODE_SERVER_FAILURE;
}

DNS_STATUS WINAPI DnsQuery_UTF8(const char *name, WORD type, DWORD options, void *extra, void **results, void **reserved)
{
    return DnsQuery_A(name, type, options, extra, results, reserved);
}

VOID WINAPI DnsRecordListFree(void *records, int free_type)
{
    /* No query here ever returns records, so there is nothing to free. */
    (void)records;
    (void)free_type;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) DisableThreadLibraryCalls(instance);
    return TRUE;
}
