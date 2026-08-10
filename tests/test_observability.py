from types import SimpleNamespace

from datapilot.observability import UsageCollector, invoke_observed


class ConfigurableModel:
    def invoke(self, prompt, config=None):
        callback = config["callbacks"][0]
        message = SimpleNamespace(
            usage_metadata={"input_tokens": 8, "output_tokens": 3, "total_tokens": 11}
        )
        callback.on_llm_end(SimpleNamespace(generations=[[SimpleNamespace(message=message)]]))
        return "ok"


def test_usage_collector_records_model_tokens():
    result, usage = invoke_observed(ConfigurableModel(), "question")
    assert result == "ok"
    assert usage == {"input_tokens": 8, "output_tokens": 3, "total_tokens": 11}


def test_usage_collector_ignores_missing_metadata():
    collector = UsageCollector()
    collector.on_llm_end(SimpleNamespace(generations=[]))
    assert collector.usage["total_tokens"] == 0
