<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.8.0-beta.1 | Date: 2026-09-01 -->

# Public scope symbols

Public GitHub source, tests, workflows, logs, tags and release assets must not contain exact host, OS-user, home-directory, LAN, share or credential-store identity.

Allowed public references:

```yaml
scopes:
  - host_ref: HOST_A
    identity_ref: PRIVILEGED_USER
  - host_ref: HOST_A
    identity_ref: SERVICE_USER
  - host_ref: HOST_B
    identity_ref: PRIVILEGED_USER
  - host_ref: HOST_B
    identity_ref: SERVICE_USER
```

Environment placeholders `${IOT_AI_HOST_A}` and `${IOT_AI_HOST_B}` are also allowed in public docs.

Exact mappings may exist only in excluded private runtime configuration, a private evidence vault, an excluded local environment file, or an encrypted operational inventory. A public receipt may carry a salted hash of a scope, not the raw identity.
