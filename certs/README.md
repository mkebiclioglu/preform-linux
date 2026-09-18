# Trust anchor for the Linux signature check

`microsoft-identity-verification-root-2020.pem` is Microsoft's *Identity
Verification Root Certificate Authority 2020*, the root of the Trusted Signing
chain Formlabs uses to sign `PreFormServer.exe`. Linux has no Authenticode trust
store, so `preform-linux install` hands this file to `osslsigncode` as the only
accepted root (for the signature and the timestamp countersignature) and also
requires the leaf subject to carry `CN=Formlabs Inc.` and `O=Formlabs Inc.`.

Source: https://www.microsoft.com/pkiops/certs/Microsoft%20Identity%20Verification%20Root%20Certificate%20Authority%202020.crt
SHA-256 fingerprint (pinned in `bin/preform-linux`):
`53:67:F2:0C:7A:DE:0E:2B:CA:79:09:15:05:6D:08:6B:72:0C:33:C1:FA:2A:26:61:AC:F7:87:E3:29:2E:12:70`
