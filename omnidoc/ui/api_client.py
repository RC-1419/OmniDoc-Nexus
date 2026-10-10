"""A small client for the Omnidoc API. The Streamlit app uses it, and any other Python frontend could too.
It knows nothing about the database or the AI keys: everything goes through the HTTP API."""
import httpx


API_PREFIX = "/v1"  # the API version this client speaks


class ApiError(Exception):
    def __init__(self, status: int, detail: str, retry_after: int | None = None):
        super().__init__(detail)
        self.status, self.detail, self.retry_after = status, detail, retry_after


class Unauthorized(ApiError):
    """The login token is missing, wrong or expired."""


def _detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except Exception:
        detail = None
    # validation errors: [{"loc": [...], "msg": "..."}]
    if isinstance(detail, list):
        detail = "; ".join(str(d.get("msg", "invalid input")) for d in detail)
    return str(detail) if detail else f"Server error ({response.status_code})"


class ApiClient:
    def __init__(self, base_url: str, token: str | None = None, client_ip: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        # the visitor's real address, passed on so the API's per-address limits work
        self.client_ip = client_ip

    def _request(self, method: str, path: str, *, timeout: float = 30, **kwargs):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        if self.client_ip:
            headers["X-Forwarded-For"] = self.client_ip
        try:
            r = httpx.request(method, self.base_url + API_PREFIX +
                              path, headers=headers, timeout=timeout, **kwargs)
        except httpx.HTTPError:
            raise ApiError(
                0, f"Can't reach the server at {self.base_url}. Is it running?")
        if r.status_code < 400:
            return r
        retry = r.headers.get("retry-after")
        error = Unauthorized if (
            r.status_code == 401 and self.token) else ApiError
        raise error(r.status_code, _detail(r), int(retry)
                    if retry and retry.isdigit() else None)

    # --- public
    def providers(self) -> dict:
        return self._request("GET", "/providers").json()

    def signup(self, username: str, password: str, email: str | None = None) -> dict:
        body = {"username": username, "password": password}
        if email:
            body["email"] = email
        return self._request("POST", "/auth/signup", json=body).json()

    def login(self, username: str, password: str) -> str:
        r = self._request("POST", "/auth/login",
                          data={"username": username, "password": password})
        return r.json()["access_token"]

    # --- private
    def me(self) -> dict:
        return self._request("GET", "/auth/me").json()

    def people(self) -> list[dict]:
        return self._request("GET", "/people").json()

    def add_person(self, name: str, relation: str) -> dict:
        return self._request("POST", "/people", json={"name": name, "relation": relation}).json()

    def documents(self) -> list[dict]:
        return self._request("GET", "/documents").json()

    def upload(self, filename: str, data: bytes, mime: str, person_id: int | None = None,
               doc_type: str | None = None) -> dict:
        form = {}
        if person_id is not None:
            form["person_id"] = str(person_id)
        if doc_type:
            form["doc_type"] = doc_type
        return self._request("POST", "/documents", timeout=180,  # scanning an image can take a while
                             files={"file": (filename, data, mime)}, data=form).json()

    def file(self, document_id: int) -> bytes:
        return self._request("GET", f"/documents/{document_id}/file", timeout=60).content

    def set_field(self, document_id: int, name: str, value: str) -> bool:
        self._request(
            "PUT", f"/documents/{document_id}/fields/{name}", json={"value": value})
        return True

    def delete_document(self, document_id: int) -> bool:
        self._request("DELETE", f"/documents/{document_id}")
        return True

    def chat(self, message: str, history: list[dict], provider: str | None = None) -> dict:
        body = {"message": message, "history": history}
        if provider:
            body["provider"] = provider
        return self._request("POST", "/chat", timeout=120, json=body).json()

    def confirm_email(self, token: str, provider: str | None = None) -> dict:
        body = {"token": token}
        if provider:
            body["provider"] = provider
        return self._request("POST", "/chat/confirm-email", timeout=60, json=body).json()
