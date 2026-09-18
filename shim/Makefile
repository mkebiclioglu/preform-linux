# Builds dnsapi.dll, the shim that lets PreFormServer start under Wine < 11.13.
CC      ?= x86_64-w64-mingw32-gcc
OBJDUMP ?= x86_64-w64-mingw32-objdump
CFLAGS  ?= -O2 -Wall -Wextra
EXPORTS  = DnsExtractRecordsFromMessage_W DnsFree DnsQueryEx DnsStartMulticastQuery DnsStopMulticastQuery DnsWriteQuestionToBuffer_W

dnsapi.dll: dnsapi.c dnsapi.def
	$(CC) $(CFLAGS) -shared -static-libgcc -Wl,--no-insert-timestamp -o $@ dnsapi.c dnsapi.def -lkernel32

check: dnsapi.dll
	@for s in $(EXPORTS); do $(OBJDUMP) -p $< | grep -qw "$$s" || { echo "missing export $$s"; exit 1; }; done
	@echo "dnsapi.dll exports: $(EXPORTS)"

clean:
	rm -f dnsapi.dll

.PHONY: check clean
