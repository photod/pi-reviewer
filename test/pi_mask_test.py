#!/usr/bin/env python3
"""Tests for pi-mask.py — real keys redacted, key names kept, real code left alone (precision).

All fixtures are SYNTHETIC: fake keys and IDs with correct public prefixes,
lengths, and checksums; they are not real secrets and are safe to share.
"""
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import tempfile

_p = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "pi-mask.py"
_spec = importlib.util.spec_from_file_location("pi_mask", _p)
pi_mask = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pi_mask)
mask = pi_mask.mask_text

ok = True


def check(name, cond):
    global ok
    print(f"{'PASS' if cond else 'FAIL'} {name}")
    ok = ok and cond


def active_groups(*names):
    config = pi_mask.default_config()
    config["groups"] = {name: False for name in config["groups"]}
    for name in names:
        config["groups"][name] = True
    return pi_mask.build_active_rules(config)


def active_country(country):
    config = pi_mask.default_config()
    config["groups"] = {name: False for name in config["groups"]}
    config["national_ids"][country] = True
    return pi_mask.build_active_rules(config)


A60 = "a" * 60
default = pi_mask.default_config()
check("default groups are exactly the documented lean set", default["groups"] == {
    "llm-keys": True, "cloud-keys": True, "regional-cloud": False,
    "git-tokens": True, "private-keys": True, "db-uris": True,
    "payments": True, "monitoring": False, "messaging": True,
    "registrars-hosting": False, "regional-services": False,
    "generic-entropy": False,
})
check("all national IDs are disabled by default", not any(default["national_ids"].values()))
# --- POSITIVE: real keys must be redacted, and the key NAME/prefix must survive ---
oai = f"OPENAI_API_KEY=sk-proj-{A60}T3BlbkFJ{A60}"
m = mask(oai)
check("openai redacted", "REDACTED:openai" in m and "T3BlbkFJ" not in m)
check("openai keeps name+prefix", m.startswith("OPENAI_API_KEY=sk-proj-"))

ant = f"key: sk-ant-api03-{'b' * 93}AA"
check("anthropic redacted", "REDACTED:anthropic" in mask(ant))

check("aws akid redacted", "REDACTED:aws-akid" in mask("AKIAIOSFODNN7EXAMPLE"))
check("github pat redacted", "REDACTED:github-pat" in mask("ghp_" + "a" * 36))
check("google aistudio redacted", "REDACTED:google-ai" in mask("AIza" + "b" * 35))
check("openai legacy redacted", "REDACTED:openai-legacy" in mask("sk-" + "a" * 20 + "T3BlbkFJ" + "b" * 20))
check("openrouter redacted", "REDACTED:openrouter" in mask("sk-or-v1-" + "a" * 64))
check("huggingface redacted", "REDACTED:huggingface" in mask("hf_" + "a" * 34))
check("gcp oauth redacted", "REDACTED:gcp-oauth" in mask("GOCSPX-" + "a" * 28))
check("minimax redacted", "REDACTED:minimax" in mask("sk-cp-" + "x" * 119))
check("kimi-coding redacted", "REDACTED:kimi-coding" in mask("sk-kimi-" + "y" * 40))
check("stripe live redacted", "REDACTED:stripe" in mask("sk_live_" + "z" * 30))
# v2 documents generic-entropy as opt-in, so this no longer redacts by default.
check("mimo generic disabled by default", "REDACTED" not in mask("MIMO_API_KEY=tp-seq7vq2Xk9Lm3Qp8Rt5Zw1Bd4Nf6"))
check("sendgrid redacted by default (messaging now on)", "REDACTED:sendgrid" in mask("SG." + "A" * 22 + "." + "b" * 43))
check("npm redacted by default (messaging now on)", "REDACTED:npm" in mask("npm_" + "a" * 36))
check("slack redacted by default (messaging now on)", "REDACTED:slack-bot" in mask("xoxb-" + "1" * 11 + "-" + "2" * 11 + "-" + "a" * 28))

# cloud-keys: AWS secret access key (40-char base64, no prefix) — keyword-gated so a bare 40-char blob isn't touched.
_cloud = active_groups("cloud-keys")
_awssec = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"   # canonical AWS example secret, 40 chars
check("AWS secret key with keyword redacted", "REDACTED:aws-secret" in mask("aws_secret_access_key = " + _awssec, _cloud))
check("AWS secret needs the keyword (bare 40-char untouched)", "REDACTED" not in mask("blob = " + _awssec, _cloud))
check("AWS AKID still redacted alongside", "REDACTED:aws-akid" in mask("AKIAIOSFODNN7EXAMPLE", _cloud))

# --- PHASE 2 PREFIX GROUPS: opt-in groups scan only when explicitly active ---
regional = active_groups("regional-cloud")
do_token = "dop_v1_" + "a1" * 32
check("regional cloud redacted", "REDACTED:digitalocean" in mask(do_token, regional) and mask(do_token, regional).startswith("dop_v1_"))
check("regional cloud code untouched", "REDACTED" not in mask("class EXOClient: pass", regional))

regional_services = active_groups("regional-services")
yandex_oauth = "y0_" + "a" * 35
check("regional services toggle redacts Yandex OAuth", "REDACTED:yandex-oauth" in mask(yandex_oauth, regional_services))
check("regional cloud excludes Yandex OAuth service token", "REDACTED" not in mask(yandex_oauth, regional))
check("only regional-cloud does not redact OpenAI", "REDACTED" not in mask(oai, regional))

registrars = active_groups("registrars-hosting")
cf_token = "cfut_" + "AbCd0123_-" * 4
check("registrar token redacted", "REDACTED:cloudflare-token" in mask(cf_token, registrars) and mask(cf_token, registrars).startswith("cfut_"))
check("registrar code untouched", "REDACTED" not in mask("def vercel_adapter(vcp_id): return vcp_id", registrars))

payments = active_groups("payments")
square = "sq0atp-" + "AbCd0123_-" * 3
check("square token redacted", "REDACTED:square" in mask(square, payments) and mask(square, payments).startswith("sq0atp-"))
check("stripe webhook secret redacted", "REDACTED:stripe-whsec" in mask("whsec_" + "a" * 32, payments))
check("plaid token redacted", "REDACTED:plaid" in mask("access-sandbox-" + "a" * 8 + "-" + "b" * 4 + "-" + "c" * 4 + "-" + "d" * 4 + "-" + "e" * 12, payments))
check("shopify token redacted", "REDACTED:shopify" in mask("shpat_" + "a" * 32, payments))
png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
eaaa_token = "EAAA" + "AbCd0123_-" * 3
check("square EAAA does not redact PNG data", mask(png_data, payments) == png_data)
check("square EAAA needs keyword", "REDACTED" not in mask(eaaa_token, payments))
check("square EAAA keyword redacted", "REDACTED:square" in mask("square token=" + eaaa_token, payments))
check("mollie shape needs keyword", "REDACTED" not in mask("value = live_" + "a" * 30, payments))
check("mollie env keyword gates token", "REDACTED:mollie" in mask("MOLLIE_API_KEY=live_" + "a" * 30, payments))

monitoring = active_groups("monitoring")
sentry = "sntryu_" + "AbCd0123+/=_" * 4
check("monitoring token redacted", "REDACTED:sentry-token" in mask(sentry, monitoring) and mask(sentry, monitoring).startswith("sntryu_"))
check("monitoring bare hex untouched", "REDACTED" not in mask("digest = " + "a1" * 16, monitoring))

messaging = active_groups("messaging")
sendgrid = "SG." + "A" * 22 + "." + "b" * 43
check("messaging token redacted", "REDACTED:sendgrid" in mask(sendgrid, messaging) and mask(sendgrid, messaging).startswith("SG."))
check("twilio hex needs keyword", "REDACTED" not in mask("constant = AC" + "a1" * 16, messaging))
check("twilio env keyword gates sid", "REDACTED:twilio-sid" in mask("TWILIO_ACCOUNT_SID=AC" + "a1" * 16, messaging))

git_tokens = active_groups("git-tokens")
check("gitlab variants complete", "REDACTED:gitlab" in mask("gldt-" + "a" * 30, git_tokens))
check("github fine-grained PAT redacted", "REDACTED:github-fine" in mask("github_pat_" + "a" * 82, git_tokens))
check("git token near miss untouched", "REDACTED" not in mask("ghp_short", git_tokens))

# --- DB URIs: redact password only; documented placeholders remain readable ---
db_rules = active_groups("db-uris")
db_uri = "postgresql://reviewer:S3cr3t-value@db.example/app"
db_masked = mask(db_uri, db_rules)
check("db uri password redacted", "reviewer:‹REDACTED:db-uri-creds" in db_masked and "@db.example/app" in db_masked and "S3cr3t-value" not in db_masked)
check("db uri placeholder untouched", mask("postgres://user:changeme@localhost/db", db_rules) == "postgres://user:changeme@localhost/db")
for placeholder in ("REPLACE_ME", "YOUR_PASSWORD_HERE", "****", "...", "placeholder", "example", "redacted"):
    uri = "postgres://user:" + placeholder + "@localhost/db"
    check("db uri placeholder " + placeholder + " untouched", mask(uri, db_rules) == uri)
check("db uri high-entropy password redacted", "REDACTED:db-uri-creds" in mask("postgres://user:R7!vK2#mQ9@localhost/db", db_rules))
check("basic auth password redacted", "REDACTED:basic-auth-url" in mask("https://user:real-secret@example.test/path", db_rules))

# --- Private-key blocks: markers survive masking; private rows never enter preview ---
pem_body = "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo="
pem = "-----BEGIN RSA PRIVATE KEY-----\n" + pem_body + "\n-----END RSA PRIVATE KEY-----"
putty_body = "cHV0dHktcHJpdmF0ZS1yb3ctMQ==\ncHV0dHktcHJpdmF0ZS1yb3ctMg==\n"
putty = (
    "PuTTY-User-Key-File-3: ssh-rsa\nEncryption: none\nComment: test\n"
    "Public-Lines: 1\nQUJD\nPrivate-Lines: 2\n" + putty_body + "Private-MAC: deadbeef"
)
ssh2_body = "U1NIMi1QUklWQVRFLVJPVy0x\nU1NIMi1QUklWQVRFLVJPVy0y"
ssh2 = "---- BEGIN SSH2 PRIVATE KEY ----\n" + ssh2_body + "\n---- END SSH2 PRIVATE KEY ----"
pgp = "-----BEGIN PGP PRIVATE KEY BLOCK-----\nQUJDREVGR0g=\n-----END PGP PRIVATE KEY BLOCK-----"
gcp_sa = '"private_key": "-----BEGIN PRIVATE KEY-----\\nQUJDREVGR0g=\\n-----END PRIVATE KEY-----"'
private_rules = active_groups("private-keys")
for rule_name, block, body_text, begin, end in (
    ("pem-privkey", pem, pem_body, "-----BEGIN RSA PRIVATE KEY-----", "-----END RSA PRIVATE KEY-----"),
    ("putty-ppk", putty, putty_body, "PuTTY-User-Key-File-3:", "Private-MAC:"),
    ("ssh2-privkey", ssh2, ssh2_body, "---- BEGIN SSH2 PRIVATE KEY ----", "---- END SSH2 PRIVATE KEY ----"),
):
    redacted = mask(block, private_rules)
    check(rule_name + " block redacted", "REDACTED:" + rule_name in redacted and body_text not in redacted)
    check(rule_name + " markers kept", begin in redacted and end in redacted)
check("public key block untouched", "REDACTED" not in mask("-----BEGIN PUBLIC KEY-----\nQUJD\n-----END PUBLIC KEY-----", private_rules))
check("PGP private block redacted", "REDACTED:pgp-privkey" in mask(pgp, private_rules))
check("GCP service-account private key redacted", "REDACTED:gcp-sa-json" in mask(gcp_sa, private_rules))

# --- GROUP: national IDs — country-gated shape -> proximity -> checksum pipeline ---
check("Luhn helper vector", pi_mask.luhn("79927398713") and not pi_mask.luhn("79927398714"))
check("Verhoeff helper vector", pi_mask.verhoeff("2363") and not pi_mask.verhoeff("2364"))
check("mod11 helper vector", pi_mask.mod11_weighted("111222333", (9, 8, 7, 6, 5, 4, 3, 2, -1)) == 0)
check("mod97 helper vector", pi_mask.mod97("GB82WEST12345698765432") and not pi_mask.mod97("GB83WEST12345698765432"))
# --- COUNTRY: US ---
us_ids = active_country("US")
check("US valid SSN with keyword redacted", "REDACTED:ssn" in mask("ssn: 123-45-6789", us_ids))
check("US invalid SSN shape untouched", "REDACTED" not in mask("ssn: 000-45-6789", us_ids))
check("US SSN requires keyword", "REDACTED" not in mask("value 123-45-6789", us_ids))
check("US valid ABA redacted", "REDACTED:aba-routing" in mask("ABA routing 000000000", us_ids))
check("US invalid ABA checksum untouched", "REDACTED" not in mask("ABA routing 000000001", us_ids))
check("US ABA requires keyword", "REDACTED" not in mask("value 000000000", us_ids))
check("US valid NPI redacted", "REDACTED:npi" in mask("NPI 1234567893", us_ids))
check("US invalid NPI checksum untouched", "REDACTED" not in mask("NPI 1234567894", us_ids))
check("US NPI requires keyword", "REDACTED" not in mask("value 1234567893", us_ids))
check("US shape-safe MBI redacted", "REDACTED:mbi" in mask("1A23B45CD67", us_ids))

# --- COUNTRY: CA ---
ca_ids = active_country("CA")
check("CA valid SIN redacted", "REDACTED:sin" in mask("046 454 286", ca_ids))
check("CA invalid SIN checksum untouched", "REDACTED" not in mask("046 454 287", ca_ids))
check("CA unformatted SIN requires keyword", "REDACTED" not in mask("046454286", ca_ids))
check("CA unformatted SIN with keyword redacted", "REDACTED:sin" in mask("SIN 046454286", ca_ids))
check("CA shape-safe BN redacted", "REDACTED:bn" in mask("123456789RC0001", ca_ids))

# --- COUNTRY: GB ---
gb_ids = active_country("GB")
check("GB shape-safe NINO redacted", "REDACTED:nino" in mask("AB123456C", gb_ids))
check("GB invalid NINO prefix untouched", "REDACTED" not in mask("BG123456C", gb_ids))

# --- COUNTRY: DE ---
de_ids = active_country("DE")
check("DE valid Steuer-ID redacted", "REDACTED:steuer-id" in mask("Steuer-ID 86095742719", de_ids))
check("DE invalid Steuer-ID checksum untouched", "REDACTED" not in mask("Steuer-ID 86095742718", de_ids))
check("DE tripled-digit Steuer-ID untouched", "REDACTED" not in mask("Steuer-ID 23456789224", de_ids))
check("DE Steuer-ID requires keyword", "REDACTED" not in mask("value 86095742719", de_ids))

# --- COUNTRY: FR ---
fr_ids = active_country("FR")
check("FR valid NIR redacted", "REDACTED:nir" in mask("180027501234525", fr_ids))
check("FR invalid NIR checksum untouched", "REDACTED" not in mask("180027501234526", fr_ids))

# --- COUNTRY: ES ---
es_ids = active_country("ES")
check("ES valid DNI redacted", "REDACTED:dni" in mask("12345678Z", es_ids))
check("ES invalid DNI checksum untouched", "REDACTED" not in mask("12345678A", es_ids))
check("ES valid NIE redacted", "REDACTED:nie" in mask("X1234567L", es_ids))
check("ES invalid NIE checksum untouched", "REDACTED" not in mask("X1234567A", es_ids))

# --- COUNTRY: IT ---
it_ids = active_country("IT")
check("IT valid Codice Fiscale redacted", "REDACTED:codice-fiscale" in mask("RSSMRA85T10A562S", it_ids))
check("IT invalid Codice Fiscale checksum untouched", "REDACTED" not in mask("RSSMRA85T10A562A", it_ids))

# --- COUNTRY: PL ---
pl_ids = active_country("PL")
check("PL valid PESEL redacted", "REDACTED:pesel" in mask("PESEL 44051401458", pl_ids))
check("PL invalid PESEL checksum untouched", "REDACTED" not in mask("PESEL 44051401459", pl_ids))
check("PL PESEL requires keyword", "REDACTED" not in mask("value 44051401458", pl_ids))

# --- COUNTRY: NL ---
nl_ids = active_country("NL")
check("NL valid BSN redacted", "REDACTED:bsn" in mask("BSN 111222333", nl_ids))
check("NL invalid BSN checksum untouched", "REDACTED" not in mask("BSN 111222334", nl_ids))
check("NL BSN requires keyword", "REDACTED" not in mask("value 111222333", nl_ids))

# --- COUNTRY: EU-IBAN ---
iban_ids = active_country("EU-IBAN")
check("EU valid IBAN redacted", "REDACTED:iban" in mask("GB82WEST12345698765432", iban_ids))
check("EU invalid IBAN checksum untouched", "REDACTED" not in mask("GB83WEST12345698765432", iban_ids))

# --- COUNTRY: BR ---
br_ids = active_country("BR")
cpf = "529.982.247-25"
check("BR valid CPF redacted", "REDACTED:cpf" in mask(cpf, br_ids))
check("BR invalid CPF checksum untouched", "REDACTED" not in mask("529.982.247-26", br_ids))
check("BR valid CNPJ redacted", "REDACTED:cnpj" in mask("04.252.011/0001-10", br_ids))
check("BR invalid CNPJ checksum untouched", "REDACTED" not in mask("04.252.011/0001-11", br_ids))
check("BR CPF disabled by default", "REDACTED" not in mask(cpf))

# --- COUNTRY: PAN ---
pan_ids = active_country("PAN")
check("card PAN valid IIN and Luhn redacted", "REDACTED:card-pan" in mask("4999 9999 9999 9996", pan_ids))
check("card PAN invalid Luhn untouched", "REDACTED" not in mask("4999 9999 9999 9997", pan_ids))
check("card PAN disabled by default", "REDACTED" not in mask("4999 9999 9999 9996"))

# --- COUNTRY: RU ---
ru_ids = active_country("RU")
for rule_name, labelled_value in (
    ("inn-10", "ИНН 7707083893"),
    ("inn-12", "ИНН 500100732259"),
    ("snils", "СНИЛС 112-233-445 95"),
    ("ogrn", "1027700132195"),
    ("ogrnip", "304500116000157"),
):
    check("RU valid " + rule_name + " redacted", "REDACTED:" + rule_name in mask(labelled_value, ru_ids))
check("RU invalid checksum untouched", "REDACTED" not in mask("ИНН 7707083894", ru_ids))
check("RU INN-12 invalid checksum untouched", "REDACTED" not in mask("ИНН 500100732258", ru_ids))
check("RU SNILS invalid checksum untouched", "REDACTED" not in mask("СНИЛС 112-233-445 94", ru_ids))
check("RU OGRN invalid checksum untouched", "REDACTED" not in mask("1027700132194", ru_ids))
check("RU OGRNIP invalid checksum untouched", "REDACTED" not in mask("304500116000158", ru_ids))
check("RU INN requires keyword", "REDACTED" not in mask("value 7707083893", ru_ids))

# --- COUNTRY: KZ ---
kz_ids = active_country("KZ")
check("KZ valid IIN redacted", "REDACTED:iin" in mask("ИИН 880517450312", kz_ids))
check("KZ valid BIN redacted", "REDACTED:bin" in mask("БИН 141140001448", kz_ids))
check("KZ invalid checksum untouched", "REDACTED" not in mask("ИИН 880517450313", kz_ids))
check("KZ BIN invalid checksum untouched", "REDACTED" not in mask("БИН 141140001449", kz_ids))
check("KZ IIN requires keyword", "REDACTED" not in mask("value 880517450312", kz_ids))

ru_kz_config = pi_mask.default_config()
ru_kz_config["groups"] = {name: False for name in ru_kz_config["groups"]}
ru_kz_config["national_ids"].update({"RU": True, "KZ": True})
ru_kz_ids = pi_mask.build_active_rules(ru_kz_config)
check("12-digit collision dispatches ИНН", "REDACTED:inn-12" in mask("ИНН 500100732259", ru_kz_ids))
check("12-digit collision dispatches ИИН", "REDACTED:iin" in mask("ИИН 880517450312", ru_kz_ids))
check("12-digit collision dispatches БИН", "REDACTED:bin" in mask("БИН 141140001448", ru_kz_ids))

# --- COUNTRY: IN ---
in_ids = active_country("IN")
check("IN valid Aadhaar redacted", "REDACTED:aadhaar" in mask("Aadhaar 2345 6789 0124", in_ids))
check("IN invalid Aadhaar checksum untouched", "REDACTED" not in mask("Aadhaar 2345 6789 0125", in_ids))
check("IN Aadhaar requires keyword", "REDACTED" not in mask("value 2345 6789 0124", in_ids))
check("IN shape-safe PAN redacted", "REDACTED:pan-in" in mask("ABCPA1234F", in_ids))
check("IN shape-safe GSTIN redacted", "REDACTED:gstin" in mask("22AAAAA0000A1Z5", in_ids))
check("IN shape-safe IFSC redacted", "REDACTED:ifsc" in mask("ZZZZ0001234", in_ids))

# --- COUNTRY: JP ---
jp_ids = active_country("JP")
check("JP valid MyNumber redacted", "REDACTED:my-number" in mask("マイナンバー 123456789018", jp_ids))
check("JP invalid MyNumber checksum untouched", "REDACTED" not in mask("マイナンバー 123456789019", jp_ids))
check("JP MyNumber requires keyword", "REDACTED" not in mask("value 123456789018", jp_ids))
check("JP valid Corp-Number redacted", "REDACTED:corp-number" in mask("法人番号 7123456789012", jp_ids))
check("JP mod-9 zero-remainder Corp-Number redacted", "REDACTED:corp-number" in mask("法人番号 9608738123045", jp_ids))
check("JP invalid Corp-Number checksum untouched", "REDACTED" not in mask("法人番号 9608738123044", jp_ids))

# --- COUNTRY: SG ---
sg_ids = active_country("SG")
check("SG valid NRIC redacted", "REDACTED:nric-fin" in mask("S1234567D", sg_ids))
check("SG invalid NRIC checksum untouched", "REDACTED" not in mask("S1234567A", sg_ids))

# --- COUNTRY: ID ---
id_ids = active_country("ID")
check("ID plausible NIK redacted", "REDACTED:nik" in mask("NIK 3174010101900001", id_ids))
check("ID invalid NIK date untouched", "REDACTED" not in mask("NIK 3174013202900001", id_ids))
check("ID NIK requires keyword", "REDACTED" not in mask("value 3174010101900001", id_ids))

# --- COUNTRY: TH ---
th_ids = active_country("TH")
check("TH valid ThaiID redacted", "REDACTED:thai-id" in mask("Thai ID 1101700207030", th_ids))
check("TH invalid ThaiID checksum untouched", "REDACTED" not in mask("Thai ID 1101700207031", th_ids))
check("TH ThaiID requires keyword", "REDACTED" not in mask("value 1101700207030", th_ids))

# --- COUNTRY: MY ---
my_ids = active_country("MY")
check("MY plausible MyKad redacted", "REDACTED:mykad" in mask("MyKad 900101-14-5678", my_ids))
check("MY invalid MyKad date untouched", "REDACTED" not in mask("MyKad 901332-14-5678", my_ids))
check("MY MyKad requires keyword", "REDACTED" not in mask("value 900101-14-5678", my_ids))

# --- COUNTRY: AR ---
ar_ids = active_country("AR")
check("AR valid CUIT redacted", "REDACTED:cuit" in mask("20-12345678-6", ar_ids))
check("AR invalid CUIT checksum untouched", "REDACTED" not in mask("20-12345678-7", ar_ids))
check("AR CUIT check-10 maps to 9", "REDACTED:cuit" in mask("20-10000411-9", ar_ids))
check("AR keyword DNI redacted", "REDACTED:dni-ar" in mask("DNI 12345678", ar_ids))
check("AR bare DNI untouched", "REDACTED" not in mask("value 12345678", ar_ids))

# --- COUNTRY: CL ---
cl_ids = active_country("CL")
check("CL valid RUT redacted", "REDACTED:rut" in mask("12.345.678-5", cl_ids))
check("CL invalid RUT checksum untouched", "REDACTED" not in mask("12.345.678-6", cl_ids))

# --- COUNTRY: MX ---
mx_ids = active_country("MX")
check("MX valid CURP redacted", "REDACTED:curp" in mask("GODE561231HDFRRN00", mx_ids))
check("MX invalid CURP checksum untouched", "REDACTED" not in mask("GODE561231HDFRRN01", mx_ids))
check("MX valid RFC redacted", "REDACTED:rfc" in mask("GODE561231GR8", mx_ids))
check("MX invalid RFC checksum untouched", "REDACTED" not in mask("GODE561231GR9", mx_ids))
check("MX canonical RFC VACE valid", pi_mask.validate_rfc("VACE460910SX5"))
check("MX canonical RFC MAHM valid", pi_mask.validate_rfc("MAHM670102NJ1"))
check("MX format-only VACE checksum invalid", not pi_mask.validate_rfc("VACE460910SX6"))
check("MX format-only MAHM checksum invalid", not pi_mask.validate_rfc("MAHM670102NJA"))

# --- COUNTRY: CO ---
co_ids = active_country("CO")
check("CO keyword cedula redacted", "REDACTED:cedula-co" in mask("Cédula 123456789", co_ids))
check("CO bare cedula untouched", "REDACTED" not in mask("value 123456789", co_ids))

# --- COUNTRY: PE ---
pe_ids = active_country("PE")
check("PE keyword DNI shape redacted", "REDACTED:dni-pe" in mask("DNI 12345678", pe_ids))
check("PE bare DNI untouched", "REDACTED" not in mask("value 12345678", pe_ids))

# --- COUNTRY: UY ---
uy_ids = active_country("UY")
check("UY valid CI redacted", "REDACTED:ci-uy" in mask("CI 1.234.567-2", uy_ids))
check("UY invalid CI checksum untouched", "REDACTED" not in mask("CI 1.234.567-3", uy_ids))
check("UY bare CI untouched", "REDACTED" not in mask("value 1.234.567-2", uy_ids))

# --- COUNTRY: VE ---
ve_ids = active_country("VE")
check("VE prefixed cedula redacted", "REDACTED:cedula-ve" in mask("V-12345678", ve_ids))
check("VE cedula without required hyphen untouched", "REDACTED" not in mask("V12345678", ve_ids))

example_path = _p.parent / "pi-mask.config.example.json"
example_config = json.loads(example_path.read_text(encoding="utf-8"))
check("example config has full group schema", set(example_config["groups"]) == set(pi_mask.DEFAULT_GROUPS))
check("example config has full national ID schema", set(example_config["national_ids"]) == set(pi_mask.NATIONAL_ID_COUNTRIES))

# --- NEGATIVE: real code / non-secrets must NOT be redacted (precision) ---
check("git sha untouched", "REDACTED" not in mask("commit " + "a1b2c3d4e5f6a7b8c9d0" * 2))  # 40-hex, no keyword
check("code untouched", "REDACTED" not in mask("def process(tp_id):\n    return tp_id + 1"))
check("short tp- untouched", "REDACTED" not in mask("transport = 'tp-layer'"))
check("plain word untouched", "REDACTED" not in mask("password: changeme"))  # low entropy, below floor
check("OpenAI near miss without marker untouched", "REDACTED" not in mask("sk-proj-" + "a" * 128))
check("GCP OAuth near miss untouched", "REDACTED" not in mask("GOCSPX-" + "a" * 27))
check("Azure storage near miss untouched", "REDACTED" not in mask("AccountKey=" + "a" * 86 + "=x"))
generic = active_groups("generic-entropy")
check("generic low-entropy keyword value untouched", "REDACTED" not in mask("API_KEY=" + "a" * 32, generic))
check("generic high-entropy value without keyword untouched", "REDACTED" not in mask("asset=QmFzZTY0QXNzZXRXaXRoRW50cm9weUFuZE5vS2V5d29yZA==", generic))
check("UUID untouched", "REDACTED" not in mask("id=550e8400-e29b-41d4-a716-446655440000", generic))
check("SHA-256 untouched", "REDACTED" not in mask("sha256=" + "a1" * 32, generic))
check("bare JWT untouched", "REDACTED" not in mask("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature"))
check("base64 asset untouched", "REDACTED" not in mask("data=AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=", generic))
check("short preview exposes less than half", pi_mask._preview_body("abcdefghi") == "ab…i")

# --- CLI: preview reports safely without touching files, and still supports stdin masking ---
body = A60 + "T3BlbkFJ" + A60
secret = "sk-proj-" + body
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    sample = root / "config.env"
    source = f"OPENAI_API_KEY={secret}\n"
    sample.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(_p), "--preview", str(sample)],
        cwd=root,
        text=True,
        capture_output=True,
    )
    check("preview exits zero", result.returncode == 0)
    check("preview names file line and rule", "config.env:1:" in result.stdout and "[openai]" in result.stdout)
    check("preview never prints full body", body not in result.stdout)
    check("preview leaves file unchanged", sample.read_text(encoding="utf-8") == source)

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    nested = root / "nested"
    nested.mkdir()
    (nested / "config.env").write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
    ignored = root / ".git"
    ignored.mkdir()
    (ignored / "config.env").write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(_p), "-n", str(root)],
        cwd=root,
        text=True,
        capture_output=True,
    )
    check("preview recurses directories and skips .git", "nested/config.env:1:" in result.stdout and result.stdout.count("[openai]") == 1)

result = subprocess.run(
    [sys.executable, str(_p), "-"],
    input=f"OPENAI_API_KEY={secret}",
    text=True,
    capture_output=True,
)
check("stdin masking still works", result.returncode == 0 and "REDACTED:openai" in result.stdout)

with tempfile.TemporaryDirectory() as tmp:
    sample = pathlib.Path(tmp) / "original.txt"
    source = "keep this original content"
    sample.write_text(source, encoding="utf-8")
    original_mask_text = pi_mask.mask_text
    def fail_masking(_text, _rules):
        raise RuntimeError("synthetic masking failure")
    pi_mask.mask_text = fail_masking
    original_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        result = pi_mask.main([str(_p), str(sample)])
    finally:
        sys.stderr = original_stderr
        pi_mask.mask_text = original_mask_text
    check("failed in-place masking preserves original", result == 1 and sample.read_text(encoding="utf-8") == source)

# --config is accepted in either position and enables only opt-in rule groups requested by a config.
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    config = root / "enabled.json"
    config.write_text('{"groups": {"messaging": true, "generic-entropy": true}}', encoding="utf-8")
    sample = root / "tokens.env"
    sample.write_text("SENDGRID=" + sendgrid + "\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(_p), "--preview", "--config", str(config), str(sample)],
        cwd=root,
        text=True,
        capture_output=True,
    )
    check("config path loads after preview flag", result.returncode == 0 and "[sendgrid]" in result.stdout)
    result = subprocess.run(
        [sys.executable, str(_p), "--config", str(config), "-"],
        input="MIMO_API_KEY=tp-seq7vq2Xk9Lm3Qp8Rt5Zw1Bd4Nf6",
        text=True,
        capture_output=True,
    )
    check("config enables generic entropy", result.returncode == 0 and "REDACTED:generic" in result.stdout)

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    config = root / "br.json"
    config.write_text('{"national_ids": {"BR": true}}', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(_p), "--config", str(config), "-"],
        input=cpf,
        text=True,
        capture_output=True,
    )
    check("config enables BR national IDs", result.returncode == 0 and "REDACTED:cpf" in result.stdout)

# unknown config keys are REJECTED (fail-closed), not silently ignored — a typo must not leave masking mis-set.
with tempfile.TemporaryDirectory() as _tmp:
    _bad = pathlib.Path(_tmp) / "bad.json"
    _bad.write_text('{"groups": {"llm-key": false}}', encoding="utf-8")   # typo: llm-key vs llm-keys
    _r = subprocess.run([sys.executable, str(_p), "--config", str(_bad), "-"], input="x", capture_output=True, text=True)
    check("unknown config group key rejected (fail-closed)", _r.returncode == 1 and "unknown" in _r.stderr.lower())

# the shipped example config carries a "_comment"; a leading-underscore key is allowed (else copying the
# example verbatim would fail-closed and abort every review).
_example = _p.parent / "pi-mask.config.example.json"
_re = subprocess.run([sys.executable, str(_p), "--config", str(_example), "-"], input="x", capture_output=True, text=True)
check("shipped example config loads (leading-underscore _comment allowed)", _re.returncode == 0)

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    sample = root / "private-keys.txt"
    sample.write_text(pem + "\n" + putty + "\n" + ssh2 + "\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(_p), "--preview", str(sample)],
        cwd=root,
        text=True,
        capture_output=True,
    )
    preview_lines = [line for line in result.stdout.splitlines() if "would redact" in line]
    check("block preview exits zero", result.returncode == 0)
    check("block preview emits one line per block", len(preview_lines) == 3)
    check("pem preview keeps markers", any("BEGIN RSA PRIVATE KEY" in line and "END RSA PRIVATE KEY" in line for line in preview_lines))
    check("putty preview keeps markers", any("PuTTY-User-Key-File-3:" in line and "Private-MAC:" in line for line in preview_lines))
    check("ssh2 preview keeps markers", any("BEGIN SSH2 PRIVATE KEY" in line and "END SSH2 PRIVATE KEY" in line for line in preview_lines))
    check("block preview hides every private row", all(secret_row not in result.stdout for secret_row in (pem_body, *putty_body.splitlines(), *ssh2_body.splitlines())))

# --- @-in-password: db-uri creds used to stop at the first @ (K3 dogfood finding) ---
_dburi = active_groups("db-uris")
_at_out = mask("connect postgres://user:p@ss@w0rd@dbhost:5432/app", _dburi)
check("db uri password containing @ is fully masked", "p@ss" not in _at_out and "ss@w0rd" not in _at_out)
check("db uri @-password keeps the host", "@dbhost:5432/app" in _at_out)

# --- binary / non-UTF-8 content is omitted, not staged unmasked (backstop past the extension denylist) ---
with tempfile.TemporaryDirectory() as _tmp:
    _blob = pathlib.Path(_tmp) / "notes.txt"           # text extension, but NUL bytes => actually binary
    _blob.write_bytes(b"HEAD\x00\x00 UNMATCHED_SECRET_abc123XYZ \x00 tail \x00")
    _rc = subprocess.run([sys.executable, str(_p), str(_blob)], capture_output=True)
    _body = _blob.read_bytes()
    check("binary/NUL file omitted from review", _rc.returncode == 0 and b"UNMATCHED_SECRET" not in _body and b"omitted from review" in _body)

with tempfile.TemporaryDirectory() as _tmp:
    _u16 = pathlib.Path(_tmp) / "config.env"
    _u16.write_bytes("TOKEN=sk-ant-DO-NOT-LEAK".encode("utf-16"))   # NUL-interleaved
    subprocess.run([sys.executable, str(_p), str(_u16)], check=True, capture_output=True)
    check("UTF-16 file omitted from review", b"omitted from review" in _u16.read_bytes())

print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
