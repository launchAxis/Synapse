from synapse.models import ModelManager


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
