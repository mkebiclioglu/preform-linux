# Builds dnsapi.dll, the shim that lets PreFormServer start under Wine < 11.13.
# make predefines CC, so ?= would keep the host compiler; override with MINGW_CC if needed.
CC      := $(or $(MINGW_CC),x86_64-w64-mingw32-gcc)
OBJDUMP := $(or $(MINGW_OBJDUMP),x86_64-w64-mingw32-objdump)
CFLAGS  ?= -O2 -Wall -Wextra
EXPORTS  = DnsExtractRecordsFromMessage_W DnsFree DnsQueryConfig DnsQueryEx DnsQuery_A DnsQuery_UTF8 DnsQuery_W DnsRecordListFree DnsStartMulticastQuery DnsStopMulticastQuery DnsWriteQuestionToBuffer_W

dnsapi.dll: dnsapi.c dnsapi.def
	$(CC) $(CFLAGS) -shared -static-libgcc -Wl,--no-insert-timestamp -o $@ dnsapi.c dnsapi.def -lkernel32

check: dnsapi.dll
	@for s in $(EXPORTS); do $(OBJDUMP) -p $< | grep -qw "$$s" || { echo "missing export $$s"; exit 1; }; done
	@echo "dnsapi.dll exports: $(EXPORTS)"

clean:
	rm -f dnsapi.dll

.PHONY: check clean
