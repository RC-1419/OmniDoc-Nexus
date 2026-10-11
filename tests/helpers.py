"""Small helpers shared by the tests (a hand-made PDF, a valid fake Aadhaar number, a scripted stand-in for the AI)."""
import json

from omnidoc.ingestion.fields import verhoeff_check_digit
from omnidoc.providers.llm.base import LLMProvider, LLMResponse, ToolCall

PASSWORD = "TestPass12345"
PAN, MUM_PAN = "ABCPE1234F", "MUMPM5678K"


def make_pdf(lines):
    content = "BT /F1 12 Tf 50 750 Td 14 TL " + \
        " ".join(f"({l}) Tj T*" for l in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()


def fake_aadhaar() -> str:
    base = "23456789012"
    n = base + verhoeff_check_digit(base)
    return f"{n[:4]} {n[4:8]} {n[8:]}"


def aadhaar_pdf(number: str) -> bytes:
    return make_pdf(["Government of India", f"Aadhaar number {number}",
                     "Name Test Person Address Lucknow Uttar Pradesh"])


class ScriptedLLM(LLMProvider):
    """Stands in for the AI: picks tools by keyword, and records everything it is ever shown."""
    name = "scripted"

    def __init__(self):
        self.seen = []

    @staticmethod
    def _call(name, **arguments):
        msg = {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]}
        return LLMResponse(None, [ToolCall("c1", name, arguments)], msg, "scripted")

    def chat(self, messages, tools=None, json_mode=False):
        self.seen.append(json.dumps(messages))
        last = messages[-1]
        if last["role"] == "tool":
            text = ("The documents mention Lucknow." if "lucknow" in last["content"].lower()
                    else "I couldn't find that in your documents.")
            return LLMResponse(text, [], {"role": "assistant", "content": text}, "scripted")
        q = last["content"].lower()
        if "pan number" in q:
            return self._call("get_document_field", doc_type="pan", person="me")
        if "show my aadhaar" in q:
            return self._call("show_document", doc_type="aadhaar", person="me")
        if "email my aadhaar" in q:
            return self._call("email_document", doc_type="aadhaar", to=q.split()[-1], person="me")
        if "address" in q:
            return self._call("answer_from_documents", question=q)
        text = "Hello! Ask me about your documents."
        return LLMResponse(text, [], {"role": "assistant", "content": text}, "scripted")
