# dnsapi shim

A small `dnsapi.dll` that stands in for Wine's builtin one when Wine is older
than 11.13 (in practice 11.5 to 11.12: older Wine lacks the ICU DLLs
PreFormServer 3.63.0 needs, see the README). See the comment at the top of `dnsapi.c` for why it exists and what
it does. `preform-linux install` builds and installs it automatically when
`wine --version` is below 11.13 (needs `gcc-mingw-w64-x86-64`), and removes it
when Wine is new enough. Force it on or off with `PREFORM_SHIM=1` / `PREFORM_SHIM=0`.

```
make        # builds dnsapi.dll
make check  # verifies the exports
```

Set `PREFORM_SHIM_TRACE=1` (bare metal, or `-e PREFORM_SHIM_TRACE=1` in Docker with
`PREFORM_SHIM=1`) and the shim logs every `DnsStartMulticastQuery` request
PreFormServer makes: the mDNS service name, record type and options. PreFormServer
3.63.0 asks for exactly one thing, right after it opens its HTTP port and again on
every broadcast `discover-devices`:

```
DnsStartMulticastQuery version=1 query="_formlabs_formule._tcp.local" type=12 options=0x0 interface=0
```

(type 12 is PTR.) That is the specification for a real implementation, which is
the next step if LAN discovery under Wine is wanted (see the README's *Printers*
section for what works without it).
