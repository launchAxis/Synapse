from synapse.models import ModelManager
from synapse.providers import ProviderResponse, parse_model_ref


def test_extract_model_names_from_dict_response():
    response = {
        "models": [
            {"name": "qwen2.5:3b"},
            {"model": "gemma2:2b"},
        ]
    }

    assert ModelManager._extract_model_names(response) == {"qwen2.5:3b", "gemma2:2b"}


def test_extract_model_names_from_object_response():
    class Item:
        def __init__(self, model):
            self.model = model

    class Response:
        models = [Item("llama3.2:3b")]

    assert ModelManager._extract_model_names(Response()) == {"llama3.2:3b"}


def test_model_manager_can_be_constructed_without_importing_ollama_client():
    class FakeClient:
        pass

    manager = ModelManager({"A": "model-a"}, client=FakeClient())

    assert manager.configured_models == {"A": "model-a"}


def test_model_manager_treats_explicit_ollama_refs_as_local_models():
    class FakeClient:
        def list(self):
            return {"models": [{"name": "qwen2.5:3b"}]}

    manager = ModelManager({"A": "ollama:qwen2.5:3b"}, client=FakeClient(), verbose=False)

    assert manager.refresh_available_models() == {"A": "qwen2.5:3b"}


def test_model_manager_routes_api_refs_when_provider_is_available():
    class FakeClient:
        pass

    class FakeRouter:
        def provider_available(self, provider):
            return provider == "openai"

        def chat(self, model_ref, prompt):
            ref = parse_model_ref(model_ref) if isinstance(model_ref, str) else model_ref
            assert ref.provider == "openai"
            return ProviderResponse(ok=True, text="provider response")

    manager = ModelManager({"A": "openai:gpt-test"}, client=FakeClient(), verbose=False, provider_router=FakeRouter())
    response = manager.ask("openai:gpt-test", "hello")

    assert response.ok
    assert response.text == "provider response"


def test_model_manager_marks_missing_api_refs_when_provider_key_is_absent():
    class FakeClient:
        def list(self):
            return {"models": []}

    class FakeRouter:
        def provider_available(self, provider):
            return False

    manager = ModelManager({"A": "openai:gpt-test"}, client=FakeClient(), verbose=False, provider_router=FakeRouter())

    assert manager.refresh_available_models() == {}
    assert manager.missing_models == {"A": "openai:gpt-test"}
