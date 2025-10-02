import hmac
import hashlib
from typing import Mapping

# Minimal Twilio signature verification if desired. Caller may skip.


def verify_twilio_signature(auth_token: str, url: str, params: Mapping[str, str], provided_sig: str) -> bool:
    s = url
    for k in sorted(params.keys()):
        s += k + params[k]
    mac = hmac.new(auth_token.encode("utf-8"), s.encode("utf-8"), hashlib.sha1)
    expected = mac.digest().hex()
    try:
        # Twilio signature is base64 encoded digest; but older docs used hex compare in examples.
        # For strict correctness, Twilio's X-Twilio-Signature is base64 of the raw HMAC digest.
        # Keeping hex fallback for local use if needed. Prefer using Twilio helper lib in production.
        import base64

        expected_b64 = base64.b64encode(mac.digest()).decode()
        return hmac.compare_digest(expected_b64, provided_sig) or hmac.compare_digest(expected, provided_sig)
    except Exception:
        return hmac.compare_digest(expected, provided_sig)
