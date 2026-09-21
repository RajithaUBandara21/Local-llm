from app.clients.base import ILLMClient


class FakeClient(ILLMClient):
    """Records calls; a failure can be queued for any method."""

    def __init__(self, reply=None, fail_on=None, loaded=None):
        self.reply = reply or {"response": "hello"}
        self.fail_on = fail_on
        self.loaded = loaded or []
        self.calls = []

    def _record(self, name, *args):
        self.calls.append((name, *args))
        if self.fail_on == name:
            raise RuntimeError(f"{name} failed")

    def generate(self, model, prompt, temperature):
        self._record("generate", model, prompt, temperature)
        return self.reply

    def load_model(self, model):
        self._record("load_model", model)

    def unload_model(self, model):
        self._record("unload_model", model)

    def list_loaded_models(self):
        self._record("list_loaded_models")
        return list(self.loaded)
