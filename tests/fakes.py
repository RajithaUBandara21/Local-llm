from app.clients.base import ILLMClient


class FakeClient(ILLMClient):
    """Records calls; a failure can be queued for any method.

    `replies` scripts successive generate outcomes: a string is a model reply, an
    exception is raised. Once used up (or when empty), `reply` is returned.
    """

    def __init__(self, reply=None, fail_on=None, loaded=None, replies=None):
        self.reply = reply or {"response": "hello"}
        self.fail_on = fail_on
        self.loaded = loaded or []
        self.replies = list(replies or [])
        self.calls = []
        self.generate_options = []

    def _record(self, name, *args):
        self.calls.append((name, *args))
        if self.fail_on == name:
            raise RuntimeError(f"{name} failed")

    def generate(self, model, prompt, temperature, schema=None, timeout=None):
        self._record("generate", model, prompt, temperature)
        self.generate_options.append({"schema": schema, "timeout": timeout})
        if not self.replies:
            return self.reply
        outcome = self.replies.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return {"response": outcome} if isinstance(outcome, str) else outcome

    def load_model(self, model):
        self._record("load_model", model)

    def unload_model(self, model):
        self._record("unload_model", model)

    def list_loaded_models(self):
        self._record("list_loaded_models")
        return list(self.loaded)
