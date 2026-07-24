# pi-mask v2 ruleset spec (canonical)

Compiled from research (gitleaks config + vendor docs + validator sources). This is the build spec for
`pi-mask.py` v2. Every rule has: **group** (config toggle), optional **country** (for national IDs),
a **prefix/regex**, an optional **checksum** (validate before redacting), and a **gate** (keyword-required?).
Precision-first: redacting real code is worse than missing an exotic key.

## Config (JSON, stdlib only — NO yaml dep)
`pi-mask.config.json` (searched: `--config` flag → cwd → repo root; absent = built-in defaults).
```json
{
  "groups": {
    "llm-keys": true, "cloud-keys": true, "regional-cloud": false, "git-tokens": true,
    "private-keys": true, "db-uris": true, "payments": true, "monitoring": false,
    "messaging": true, "registrars-hosting": false, "regional-services": false, "generic-entropy": false
  },
  "national_ids": { "US": false, "CA": false, "GB": false, "DE": false, "FR": false, "ES": false,
    "IT": false, "PL": false, "NL": false, "EU-IBAN": false, "RU": false, "KZ": false, "IN": false,
    "JP": false, "SG": false, "TH": false, "ID": false, "MY": false, "BR": false, "AR": false,
    "CL": false, "MX": false, "CO": false, "PE": false, "UY": false, "VE": false }
}
```
**Default (no file): cheap+high-precision+low-FP groups ON** — `llm-keys, cloud-keys, git-tokens,
private-keys, db-uris, payments, messaging` (messaging is prefix-based and low-FP). Everything else
(regional, monitoring, registrars, national_ids, generic-entropy) **OFF** — CPU-heavy / higher-FP / opt-in. Engine filters rules by the
enabled set BEFORE scanning (a disabled group costs nothing).

Rule tagging: each rule carries `group` and (national IDs) `country`; the engine builds the active rule
list from config, then scans. National-ID checksum funcs only run when that country is enabled.

---

## GROUP: llm-keys (default ON) — single-line prefix rules
| name | regex (group1=prefix-keep, group2=body) | notes |
|---|---|---|
| openai | `(sk-(?:proj\|svcacct\|admin)-)([A-Za-z0-9_-]{40,200}T3BlbkFJ[A-Za-z0-9_-]{40,200})` | `T3BlbkFJ` marker = high precision |
| openai-legacy | `(sk-)([A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20})` | |
| anthropic | `(sk-ant-(?:api03\|admin01)-)([A-Za-z0-9_-]{93}AA)` | |
| google-ai | `(AIza)([A-Za-z0-9_-]{35})` | |
| openrouter | `(sk-or-v1-)([a-f0-9]{64})` | |
| kimi-coding | `(sk-kimi-)([A-Za-z0-9]{20,})` | |
| minimax | `(sk-cp-)([A-Za-z0-9._-]{80,200})` | |
| huggingface | `(hf_)([A-Za-z0-9]{34})` | |
| groq | `(gsk_)([A-Za-z0-9]{52})` | |
| replicate | `(r8_)([A-Za-z0-9]{37})` | |
NOTE: MiMo `tp-` and bare Zhipu `32hex.16` are NOT prefix rules (2-char/low-precision) → generic-entropy only.

## GROUP: cloud-keys (default ON)
| name | regex | notes |
|---|---|---|
| aws-akid | `((?:AKIA\|ASIA\|ABIA\|ACCA\|A3T[A-Z0-9]))([A-Z2-7]{16})` | |
| aws-secret | `([A-Za-z0-9/+]{40})` (40-char base64, no prefix) | keyword-gated (line): `aws_secret_access_key`/`secret_access_key`/`aws_secret` |
| gcp-oauth | `(GOCSPX-)([A-Za-z0-9_-]{28})` | |
| gcp-privkey | (see private-keys block: `"private_key"` JSON + PEM) | |
| azure-storage | `(AccountKey=)([A-Za-z0-9+/]{86}==)` | keyword-anchored |

## GROUP: regional-cloud (default OFF)
| name | regex | notes |
|---|---|---|
| yandex-apikey | `(AQVN)([A-Za-z0-9_-]{35,38})` | |
| yandex-iam | `(t1\.)([A-Za-z0-9_-]+=*\.[A-Za-z0-9_-]{86}=*)` | |
| yandex-static | `(YC)([A-Za-z0-9_-]{38})` | |
| alibaba-akid | `(LTAI)([A-Za-z0-9]{20})` | |
| tencent-secretid | `(AKID)([A-Za-z0-9]{13,32})` | length varies |
| scaleway-akey | `(SCW)([A-Z0-9]{17})` | |
| exoscale | `(EXO)([A-Za-z0-9]{20,32})` | |
| digitalocean | `(do[pour]_v1_)([a-f0-9]{64})` | |
Keyword-anchored (no prefix; gate on env-var/keyword): Alibaba secret, Tencent SecretKey, Huawei AK/SK,
Baidu (`bce-auth-v1/`), Hetzner (`HCLOUD_TOKEN`), Vultr, Fastly (`Fastly-Key`), Linode.

## GROUP: git-tokens (default ON)
| name | regex |
|---|---|
| github | `(gh[posur]_)([0-9A-Za-z]{36})` |
| github-fine | `(github_pat_)(\w{82})` |
| gitlab | `(gl(?:pat\|dt)-)([\w-]{20,50})` |

## GROUP: registrars-hosting (default OFF)
| name | regex |
|---|---|
| porkbun | `((?:pk1\|sk1)_)([0-9a-z]{58,64})` |
| cloudflare-token | `(cf(?:ut\|at)_)([A-Za-z0-9_-]{40,45})` |
| cloudflare-key | `(cfk_)([A-Za-z0-9]{40,45})` |
| netlify | `(nf[pcoub]_)([A-Za-z0-9_-]{36})` |
| vercel | `(vcp_)([A-Za-z0-9]{20,40})` |
| ionos | `([0-9a-f]{32})(\.[A-Za-z0-9_-]{80,90})` |
| godaddy | `(sso-key )([A-Za-z0-9_]{10,30}:[A-Za-z0-9_]{10,50})` |
Keyword-anchored: Namecheap, Name.com, Gandi, Bunny (`AccessKey`), Vultr.

## GROUP: payments (default ON)
| name | regex |
|---|---|
| stripe | `((?:sk\|rk)_(?:live\|test\|prod)_)([A-Za-z0-9]{10,99})` |
| stripe-whsec | `(whsec_)([A-Za-z0-9]{32,64})` |
| square | `((?:sq0atp-\|EAAA))([A-Za-z0-9_-]{22,60})` |
| braintree | `(access_token\$(?:production\|sandbox)\$)([a-f0-9]{16}\$[a-f0-9]{32})` |
| mollie | `((?:test\|live)_)([A-Za-z0-9]{30,31})` | keyword-gate `mollie` to avoid Stripe collision |
| toss | `((?:test\|live)_g?sk_)([A-Za-z0-9]{20,40})` |
| razorpay | `(rzp_(?:test\|live)_)([A-Za-z0-9]{14})` |
| yookassa | `((?:live\|test)_)([A-Za-z0-9]{20,50})` | keyword-gate `yookassa`/`shopId`; also enabled by `regional-services` |
| plaid | `(access-(?:sandbox\|development\|production)-)([0-9a-f-]{36})` |
| shopify | `(shp(?:at\|ss\|ca\|pa)_)([a-fA-F0-9]{32,64})` |
Keyword-anchored: Klarna, Wise, Revolut, GoCardless, PayPal, Coinbase, Adyen (`AQE`), CloudPayments, PayTM.

## GROUP: monitoring (default OFF)
| name | regex |
|---|---|
| sentry-dsn | `(https?://[a-f0-9]{32}(?::[a-f0-9]{32})?@(?:o\d+\.)?ingest(?:\.[a-z]+)?\.sentry\.io/)(\d+)` |
| sentry-token | `(sntry[us]_)([A-Za-z0-9+/=_-]{40,})` |
| grafana-sa | `(glsa_)([A-Za-z0-9]{32}_[A-Fa-f0-9]{8})` |
| grafana-cloud | `(glc_)(eyJ[A-Za-z0-9+/=]{32,})` |
| newrelic-user | `(NRAK-)([A-Z0-9]{27})` |
| newrelic-ingest | `(NRII-)([a-z0-9-]{32})` |
| datadog | keyword-gate `dd_api_key` + `[a-f0-9]{32}` (NEVER bare hex) |
| mailgun | `(key-)([a-f0-9]{32})` |
| mailchimp | `([0-9a-f]{32})(-us\d{1,2})` |
| circleci | keyword-gate `circle_token` + `[a-f0-9]{40}` |

## GROUP: messaging (default ON)
| name | regex |
|---|---|
| twilio-sid | `(AC)([0-9a-fA-F]{32})` | keyword-gate `twilio`/`sid` (collides w/ generic hex) |
| twilio-apikey | `(SK)([0-9a-fA-F]{32})` | keyword-gate (collides w/ Stripe/OpenAI) |
| telegram-bot | `(\d{8,10}:AA)([0-9A-Za-z_-]{33})` |
| discord-bot | `([MN][A-Za-z0-9_-]{23,25}\.[\w-]{6}\.)([\w-]{27,38})` | JWT-shaped, medium precision |
| slack-bot | `(xoxb-)([0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9-]{24,34})` |
| slack-user | `(xox[pe]-)((?:[0-9]{10,13}-){2,3}[a-zA-Z0-9-]{28,34})` |
| slack-app | `(xapp-)(\d-[A-Z0-9]+-\d+-[0-9a-f]{40,80})` |
| slack-webhook | `(hooks\.slack\.com/(?:services\|workflows\|triggers)/)([A-Za-z0-9+/]{43,56})` |
| sendgrid | `(SG\.)([A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43})` |
| npm | `(npm_)([0-9A-Za-z]{36})` |
| pypi | `(pypi-AgEIcHlwaS5vcmc)([A-Za-z0-9_-]{50,1000})` |
Regional messaging keyword-anchored: WeChat (`wx`+16hex), Feishu (`cli_`,`t-`,`u-`,`a-`), DingTalk (`SEC`+hex),
Kakao (`KakaoAK`+32hex), LINE (base64 100+, keyword-gate), VK (`vk1.a.`), Tinkoff (`t.`+80+).

## GROUP: regional-services (default OFF)
| name | regex | notes |
|---|---|---|
| yandex-oauth | `(y0_)([A-Za-z0-9_-]{35,60})` | shared across Yandex non-cloud; separate from cloud credentials |
| yookassa | (payments rule above) | also enabled by this group so regional-services has a concrete effect |

## GROUP: db-uris (default ON)
| name | regex | notes |
|---|---|---|
| db-uri-creds | `((?:postgres(?:ql)?\|mysql\|mongodb(?:\+srv)?\|redis\|amqp)://[^:\s"']+:)([^@\s"'/]+)(@)` | mask the password (group2); denylist placeholders (`password`,`changeme`,`xxx`,`<...>`) |
| basic-auth-url | `([a-z][a-z0-9+.-]*://[^:\s"'/]+:)([^@\s"'/]+)(@)` | same placeholder denylist |

## GROUP: private-keys (default ON) — MULTI-LINE BLOCK rules
Block mode: match BEGIN→END, redact the base64 body, KEEP the BEGIN/END markers. Preview collapses the whole
block to ONE line.
| name | pattern |
|---|---|
| pem-privkey | `-----BEGIN[ A-Z0-9]{0,40}PRIVATE KEY-----[\s\S]+?-----END[ A-Z0-9]{0,40}PRIVATE KEY-----` (covers OPENSSH/RSA/EC/DSA/PKCS8/ENCRYPTED) |
| pgp-privkey | `-----BEGIN PGP PRIVATE KEY BLOCK-----[\s\S]+?-----END PGP PRIVATE KEY BLOCK-----` |
| putty-ppk | `PuTTY-User-Key-File-[23]:[\s\S]+?Private-MAC:` (redact the `Private-Lines:` body) |
| ssh2-privkey | `---- BEGIN SSH2 (?:ENCRYPTED )?PRIVATE KEY ----[\s\S]+?---- END SSH2 (?:ENCRYPTED )?PRIVATE KEY ----` (4-dash + spaces) |
| gcp-sa-json | `"private_key"\s*:\s*"[\s\S]+?-----END[^"]+"` |

## GROUP: national_ids (default OFF, per-country toggle) — regex → keyword-proximity → checksum → redact
Detection order per candidate: (1) regex shape, (2) if no checksum OR ambiguous → require a context keyword
within ~±2 tokens, (3) run the country checksum, (4) redact only on pass. Distinctive-shape ones (marked
"shape-safe") may skip the keyword. 12-digit RU/KZ collision: keyword picks which checksum.

### Checksum helpers to implement
- **luhn(digits)**: right-to-left, double every 2nd, sum-reduce >9, total %10==0.
- **verhoeff(digits)**: dihedral D5 tables `d`,`p`,`inv` (Aadhaar) — standard tables (codex: use canonical Verhoeff tables).
- **mod11_weighted(digits, weights)**: `r = sum(d*w)%11`; check = per-country rule below.
- **mod97(str)**: IBAN — move first 4 chars to end, letters→(A=10..Z=35), int %97 == 1.

### Rows
| id | country | group-country | regex | checksum |
|---|---|---|---|---|
| SSN | US | US | `(?!000\|666\|9\d\d)\d{3}-?(?!00)\d{2}-?(?!0000)\d{4}` | none → keyword `ssn`/`social security` REQUIRED |
| ABA-routing | US | US | `\d{9}` | `3(d1+d4+d7)+7(d2+d5+d8)+(d3+d6+d9) %10==0`; keyword gate |
| NPI | US | US | `\d{10}` | luhn of `"80840"+first9`; keyword `npi` |
| MBI | US | US | `[0-9][A-HJ-KM-NPQ-RT-VWXY][0-9]{2}[A-HJ-KM-NPQ-RT-VWXY][0-9]{2}[A-HJ-KM-NPQ-RT-VWXY]{2}[0-9]{2}` | none; shape-safe |
| card-PAN | * | US (or own toggle `PAN`) | `(?:\d[ -]?){13,19}` | luhn + IIN-range + not-all-same; HIGH-VALUE |
| SIN | CA | CA | `\d{3}[- ]?\d{3}[- ]?\d{3}` | luhn; keyword `sin` when unformatted |
| BN | CA | CA | `\d{9}[A-Z]{2}\d{4}` | none; shape-safe |
| NINO | GB | GB | `(?!BG\|GB\|NK\|KN\|TN\|NT\|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\d{6}[A-D]` | none; shape-safe |
| Steuer-ID | DE | DE | `[1-9]\d{10}` | ISO7064 MOD11,10 + digit-repetition rule; keyword |
| NIR | FR | FR | `[12]\d{2}(0[1-9]\|1[0-2]\|20)\d{2}\d{3}\d{3}\d{2}` | `key=97-(first13 %97)`; shape-ish once 15-digit |
| DNI | ES | ES | `\d{8}[A-Z]` | mod23 table `TRWAGMYFPDXBNJZSQVHLCKE`; shape-safe |
| NIE | ES | ES | `[XYZ]\d{7}[A-Z]` | mod23, X/Y/Z→0/1/2; shape-safe |
| Codice-Fiscale | IT | IT | `[A-Z]{6}\d{2}[A-EHLMPR-T]\d{2}[A-Z]\d{3}[A-Z]` | DM1974 odd/even mod26; shape-safe |
| PESEL | PL | PL | `\d{11}` | weights `[1,3,7,9,1,3,7,9,1,3]`, check=`(10-sum%10)%10`; keyword + date-plausible |
| BSN | NL | NL | `\d{8,9}` | elfproef weights `[9,8,7,6,5,4,3,2,-1]` sum%11==0; keyword |
| IBAN | EU | EU-IBAN | `[A-Z]{2}\d{2}[A-Z0-9]{11,30}` | mod97==1 + per-country length; shape-safe |
| INN-10 | RU | RU | `\d{10}` | w `[2,4,10,3,5,9,4,6,8]`, check=`(sum%11)%10`==d10; keyword `инн` |
| INN-12 | RU | RU | `\d{12}` | 2-pass: w11=`[7,2,4,10,3,5,9,4,6,8]`→d11, w12=`[3,7,2,4,10,3,5,9,4,6,8]`→d12; keyword `инн` (disambig vs IIN/BIN) |
| SNILS | RU | RU | `\d{3}-?\d{3}-?\d{3}\s?\d{2}` | w=9..1; sum<100→c=sum; ∈{100,101}→0; >101→sum%101 (100→0); keyword |
| OGRN | RU | RU | `\d{13}` | `(first12 %11)%10`==d13 |
| OGRNIP | RU | RU | `\d{15}` | `(first14 %13)%10`==d15 (handle remainder 10/11/12) |
| IIN | KZ | KZ | `\d{12}` | 2-pass mod11: w1=`[1..11]`, if==10 w2=`[3,4,5,6,7,8,9,10,11,1,2]`; +date(1-6)/century check; keyword `иин` |
| BIN | KZ | KZ | `\d{12}` | same 2-pass mod11 (NO birthdate check; year/month + entity-type); keyword `бин` |
| Aadhaar | IN | IN | `[2-9]\d{3}\s?\d{4}\s?\d{4}` | verhoeff; keyword `aadhaar`/`uid`; MOST-SENSITIVE |
| PAN | IN | IN | `[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]` | none (private algo); shape-safe |
| GSTIN | IN | IN | `\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Za-z]Z[0-9A-Za-z]` | mod36 optional; shape-safe (embeds PAN) |
| IFSC | IN | IN | `[A-Z]{4}0[A-Z0-9]{6}` | none; shape-safe (fixed `0` pos5) |
| MyNumber | JP | JP | `\d{12}` | w=`[6,5,4,3,2,7,6,5,4,3,2]`, check=`11-(sum%11)`, >=10→0; keyword `マイナンバー`/`個人番号` |
| Corp-Number | JP | JP | `\d{13}` | mod9 over 12 base; keyword `法人番号` |
| NRIC-FIN | SG | SG | `[STFG]\d{7}[A-Z]` | w=`[2,7,6,5,4,3,2]` + offset(T/G=4) + prefix-dependent letter table; shape-safe |
| NIK | ID | ID | `\d{16}` | none; keyword `NIK`/`KTP` + province+date plausibility |
| ThaiID | TH | TH | `\d{13}` | `sum(d_i*(13-i))`, check=`(11-sum%11)%10`; keyword |
| MyKad | MY | MY | `\d{6}-?\d{2}-?\d{4}` | none; keyword `mykad` + PB-code + date |
| CPF | BR | BR | `\d{3}\.?\d{3}\.?\d{3}-?\d{2}` | 2×mod11 (w1 `[10..2]`, w2 `[11..2]`, r<2→0 else 11-r); reject all-same; shape-ish |
| CNPJ | BR | BR | `\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}` | 2×mod11 (w1 `[5,4,3,2,9,8,7,6,5,4,3,2]`, w2 prepend 6); alphanumeric-2026 variant: char=ASCII-48 |
| CUIT | AR | AR | `\d{2}-?\d{8}-?\d` | mod11 w=`[5,4,3,2,7,6,5,4,3,2]`, check=11-r (11→0) |
| DNI-AR | AR | AR | `\d{7,8}` | none; keyword `dni`/`documento` REQUIRED |
| RUT | CL | CL | `\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK]` | mod11 cyclic w `[2,3,4,5,6,7]` R→L, check 11-r (11→0,10→K); shape-ish |
| CURP | MX | MX | `[A-Z]{4}\d{6}[HM][A-Z]{2}[B-DF-HJ-NP-TV-Z]{3}[A-Z0-9]\d` | mod10 RENAPO table; shape-safe |
| RFC | MX | MX | `[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3}` | mod11 SAT table; shape-safe |
| Cedula-CO | CO | CO | `\d{6,10}` | none; keyword `cédula`/`CC`/`NUIP` REQUIRED |
| DNI-PE | PE | PE | `\d{8}` | shape + keyword only: RENIEC treats the verifier as separate from the eight-digit DNI number |
| CI-UY | UY | UY | `\d{1,2}\.?\d{3}\.?\d{3}-?\d` | mod10 w=`[2,9,8,7,6,3,4]`; left-pad to 8 digits, check=`(-sum)%10` |
| Cedula-VE | VE | VE | `[VEve]-?\d{6,8}` | none; require `V-`/`E-` prefix |

## GROUP: generic-entropy (default OFF) — LAST pass, keyword-gated
`(?i)(api[_-]?key|secret|token|password|passwd|client[_-]?secret|access[_-]?key|auth)(\s*[:=]\s*['"]?)([A-Za-z0-9+/_-]{24,})`
→ mask group3 only if Shannon entropy ≥3.5 (base64) / handles the "no distinctive prefix" regional-service &
DB-secret long tail. This is the catch-all for the keyword-anchored providers listed above.

## Redaction & preview (unchanged contract)
- Single-line: keep group1 (prefix/name), replace group2 body with `‹REDACTED:name:Nch›`.
- Block: keep BEGIN/END markers, redact body; preview shows one line per block.
- Preview (`--preview`): grep-style `path:line: <line, secret mid collapsed to …> — would redact [name]`.
- Fail-closed everywhere; national-ID checksum FAIL → skip (don't redact) rather than hard-error.
