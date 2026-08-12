import base64
import hashlib
import hmac
import json
from xml.sax.saxutils import escape


def _b64encode(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(text):
    padded = text + "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def encode_descriptor(payload, secret):
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body_token = _b64encode(body)
    signature = hmac.new(str(secret).encode("utf-8"), body_token.encode("ascii"), hashlib.sha256).digest()
    return f"{body_token}.{_b64encode(signature)}"


def decode_descriptor(token, secret):
    try:
        body_token, signature_token = str(token).split(".", 1)
        expected = hmac.new(str(secret).encode("utf-8"), body_token.encode("ascii"), hashlib.sha256).digest()
        actual = _b64decode(signature_token)
        if not hmac.compare_digest(expected, actual):
            raise ValueError("Invalid descriptor signature")
        payload = json.loads(_b64decode(body_token).decode("utf-8"))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Invalid Mustarrd descriptor") from exc
    if not isinstance(payload, dict) or int(payload.get("version") or 0) != 1:
        raise ValueError("Unsupported Mustarrd descriptor")
    return payload


def descriptor_nzb(token, subject):
    token_xml = escape(str(token))
    subject_xml = escape(str(subject), {'"': '&quot;'})
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<nzb xmlns="http://www.newzbin.com/DTD/2003/nzb">
  <head>
    <meta type="category">mustarrd</meta>
    <meta type="mustarrd">{token_xml}</meta>
  </head>
  <file poster="mustarrd" date="0" subject="{subject_xml}">
    <groups><group>mustarrd.local</group></groups>
    <segments><segment bytes="1" number="1">mustarrd@local</segment></segments>
  </file>
</nzb>'''.encode("utf-8")


def extract_descriptor_from_nzb(data):
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(data)
    except Exception as exc:
        raise ValueError("Invalid NZB XML") from exc
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "meta" and element.attrib.get("type") == "mustarrd":
            token = (element.text or "").strip()
            if token:
                return token
    raise ValueError("NZB does not contain a Mustarrd descriptor")
