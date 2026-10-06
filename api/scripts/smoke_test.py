import argparse
import io
import time
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pymupdf
from PIL import Image, ImageDraw, ImageFont

POLL_INTERVAL_S = 1.0
POLL_TIMEOUT_S = 180.0

INVOICE_LINES = (
    "SOCIETE NATIONALE D'ELECTRICITE",
    "Facture n° 2026-118 du 01/10/2026",
    "Client : Awa Diop - Dakar, Parcelles Assainies",
    "Montant a payer : 12 500 F CFA",
    "Date limite de paiement : 30/10/2026",
    "En cas de retard, des frais de 1 000 F CFA seront ajoutes.",
)


def invoice_photo() -> bytes:
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=42)
    for index, line in enumerate(INVOICE_LINES):
        draw.text((90, 140 + index * 110), line, fill="black", font=font)
    draw.rectangle((70, 100, 1170, 900), outline="black", width=4)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def invoice_pdf() -> bytes:
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((60, 90), "\n".join(INVOICE_LINES), fontsize=12)
        return bytes(pdf.tobytes())


class SmokeTest:
    def __init__(self, base_url: str, phone: str, code_provider: Callable[[], str]) -> None:
        self._client = httpx.Client(base_url=f"{base_url.rstrip('/')}/v1", timeout=60.0)
        self._phone = phone
        self._code_provider = code_provider
        self._token: str | None = None

    def call(self, method: str, path: str, expected: int = 200, **kwargs: Any) -> Any:
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        response = self._client.request(method, path, headers=headers, **kwargs)
        if response.status_code != expected:
            raise AssertionError(f"{method} {path} -> {response.status_code}: {response.text}")
        return response.json() if response.content else None

    def wait_for(self, path: str, done: Callable[[Any], bool]) -> Any:
        deadline = time.monotonic() + POLL_TIMEOUT_S
        while time.monotonic() < deadline:
            payload = self.call("GET", path)
            if done(payload):
                return payload
            time.sleep(POLL_INTERVAL_S)
        raise AssertionError(f"timeout while waiting for {path}")

    def step(self, title: str) -> None:
        print(f"\n== {title}")

    def run(self) -> None:
        self.step("Health")
        print(self.call("GET", "/health"))
        self.start_as_guest()
        document = self.explain_photo()
        self.simplify(document)
        self.ask_question(document)
        self.create_account()
        self.explain_pdf()
        self.write_letter()
        self.practice()
        self.subscribe()
        self.step("Library")
        for item in self.call("GET", "/library"):
            print(item["kind"], item["status"], item["title"])
        print("\nSmoke test passed.")

    def start_as_guest(self) -> None:
        self.step("Guest session")
        guest = self.call(
            "POST",
            "/auth/guest",
            201,
            json={"device_id": uuid.uuid4().hex, "language": "wo", "platform": "android"},
        )
        self._token = guest["access_token"]
        print("guest", guest["user"]["id"])

    def upload(self, filename: str, content: bytes, mime_type: str) -> Any:
        document = self.call(
            "POST", "/documents", 202, files=[("files", (filename, content, mime_type))]
        )
        return self.wait_for(
            f"/documents/{document['id']}",
            lambda item: item["status"] not in {"pending", "processing"},
        )

    def explain_photo(self) -> Any:
        self.step("Upload a photographed invoice")
        document = self.upload("facture.jpg", invoice_photo(), "image/jpeg")
        print(document["status"], "|", document["title"])
        print("explanation:", document["explanation"]["text"][:160])
        print("key points:", [point["title_fr"] for point in document["key_points"]])
        return document

    def simplify(self, document: Any) -> None:
        self.step("Simpler explanation")
        simple = self.call(
            "POST", f"/documents/{document['id']}/explanations", 202, json={"variant": "simple"}
        )
        print(simple["status"])
        self.wait_for(
            f"/documents/{document['id']}", lambda item: item["simple_explanation"] is not None
        )

    def ask_question(self, document: Any) -> None:
        self.step("Ask a question")
        conversation = self.call("POST", f"/documents/{document['id']}/conversation")
        exchange = self.call(
            "POST",
            f"/conversations/{conversation['id']}/messages",
            202,
            data={"text": "Avant quelle date je dois payer ?", "text_language": "fr"},
        )
        answer = self.wait_for_message(conversation["id"], exchange["answer"]["id"])
        print("answer:", answer["text_fr"])

    def wait_for_message(self, conversation_id: str, message_id: str) -> Any:
        messages = self.wait_for(
            f"/conversations/{conversation_id}/messages",
            lambda items: any(
                item["id"] == message_id and item["status"] != "pending" for item in items
            ),
        )
        return next(item for item in messages if item["id"] == message_id)

    def create_account(self) -> None:
        self.step("Create the account from the guest session")
        self.call("POST", "/auth/otp/request", json={"phone_number": self._phone})
        account = self.call(
            "POST",
            "/auth/otp/verify",
            json={
                "phone_number": self._phone,
                "code": self._code_provider(),
                "language": "wo",
                "platform": "android",
            },
        )
        self._token = account["access_token"]
        print("account", account["user"]["id"], "new:", account["is_new_account"])
        self.call("PATCH", "/me", json={"first_name": "Awa", "accept_terms": True})
        print(self.call("GET", "/me")["plan"])

    def explain_pdf(self) -> None:
        self.step("Upload a PDF")
        document = self.upload("facture.pdf", invoice_pdf(), "application/pdf")
        print(document["status"], "|", document["title"])

    def write_letter(self) -> None:
        self.step("Leeral writes for me")
        writing = self.call("POST", "/writings", 201, json={"type": "request_letter"})
        while writing["status"] == "collecting":
            step = writing["steps"][writing["current_step"]]
            self.wait_for_message(writing["conversation_id"], step["question_message_id"])
            reply = self.call(
                "POST",
                f"/writings/{writing['id']}/answers",
                202,
                data={"text": f"Réponse pour {step['field_key']}", "text_language": "fr"},
            )
            self.wait_for_message(writing["conversation_id"], reply["id"])
            writing = self.call(
                "POST", f"/writings/{writing['id']}/confirm", json={"accepted": True}
            )
            print("confirmed", step["field_key"])
        writing = self.wait_for(
            f"/writings/{writing['id']}", lambda item: item["status"] in {"ready", "failed"}
        )
        print(writing["status"], [output["kind"] for output in writing["outputs"]])

    def practice(self) -> None:
        self.step("Learn French")
        print(self.call("GET", "/learning/overview"))
        practice = self.call("POST", "/learning/sessions", 201)
        exercise = practice["exercises"][0]
        result = self.call(
            "POST",
            f"/learning/sessions/{practice['session_id']}/answers",
            json={"word_id": exercise["word_id"], "chosen_word_id": exercise["word_id"]},
        )
        print("correct:", result["is_correct"], "box:", result["box"])

    def subscribe(self) -> None:
        self.step("Leeral+ (simulated payment)")
        payment = self.call("POST", "/billing/checkout", 201, json={"method": "wave"})
        payment = self.call(
            "POST",
            f"/billing/payments/{payment['public_token']}/simulate",
            json={"outcome": "success"},
        )
        print(payment["status"], self.call("GET", "/me")["plan"])


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end check of a running Leeral API")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--phone", default="+221770000001")
    args = parser.parse_args()
    SmokeTest(args.base_url, args.phone, lambda: input("Code OTP reçu : ").strip()).run()


if __name__ == "__main__":
    main()
