# dnsapi shim

A 60-line `dnsapi.dll` that stands in for Wine's builtin one when Wine is older
than 11.13 (in practice 11.5 to 11.12: older Wine lacks the ICU DLLs
PreFormServer 3.63.0 needs, see the README). See the comment at the top of `dnsapi.c` for why it exists and what
it does. `preform-linux install` builds and installs it automatically when
`wine --version` is below 11.13 (needs `gcc-mingw-w64-x86-64`), and removes it
when Wine is new enough. Force it on or off with `PREFORM_SHIM=1` / `PREFORM_SHIM=0`.

```
make        # builds dnsapi.dll
make check  # verifies the six exports
```
