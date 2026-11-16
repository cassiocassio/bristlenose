"""One readiness answer for the in-app assistants: Azure needs all three.

A key alone let AutoCode, Signals elaboration, the catch-up and the chat lens
start with no Azure endpoint or deployment, then fail on the first call. Each
CALLER is pinned here, not only ``config.provider_not_ready``, because a helper
nobody calls is green forever.
"""

from __future__ import annotations

import pytest

from bristlenose.config import BristlenoseSettings, provider_not_ready
from bristlenose.server.refusal import RefusalError, RefusalReason

KEY = "k" * 32
ENDPOINT = "https://example-resource.openai.azure.com/"
DEPLOYMENT = "gpt-test"


def _azure(**over: str) -> BristlenoseSettings:
    fields = {
        "llm_provider": "azure",
        "azure_api_key": KEY,
        "azure_endpoint": ENDPOINT,
        "azure_deployment": DEPLOYMENT,
    }
    fields.update(over)
    return BristlenoseSettings(**fields)  # type: ignore[arg-type]


INCOMPLETE = [
    pytest.param({"azure_endpoint": ""}, "endpoint", id="no-endpoint"),
    pytest.param({"azure_deployment": ""}, "deployment", id="no-deployment"),
    pytest.param({"azure_endpoint": "   "}, "endpoint", id="blank-endpoint"),
]


class TestTheAnswer:
    def test_a_complete_azure_is_ready(self) -> None:
        assert provider_not_ready(_azure()) == ""

    @pytest.mark.parametrize(("over", "word"), INCOMPLETE)
    def test_a_key_alone_is_not_ready(self, over: dict[str, str], word: str) -> None:
        assert word in provider_not_ready(_azure(**over))

    def test_no_key_says_key(self) -> None:
        assert "API key" in provider_not_ready(_azure(azure_api_key=""))

    def test_local_needs_nothing(self) -> None:
        assert provider_not_ready(BristlenoseSettings(llm_provider="local")) == ""


class TestCallers:
    @pytest.mark.parametrize(("over", "word"), INCOMPLETE)
    def test_every_site_refuses_an_incomplete_azure(
        self, over: dict[str, str], word: str
    ) -> None:
        from bristlenose.server import autocode_catch_up, chat_lens, elaboration
        from bristlenose.server.routes import autocode

        s = _azure(**over)
        assert autocode._has_api_key(s) is False
        assert elaboration._has_api_key(s) is False
        assert autocode_catch_up.cloud_ready(s) is False
        ok, reason = chat_lens.has_usable_provider(s)
        assert not ok and word in reason

    def test_every_site_accepts_a_complete_azure(self) -> None:
        from bristlenose.server import autocode_catch_up, chat_lens, elaboration
        from bristlenose.server.routes import autocode

        s = _azure()
        assert autocode._has_api_key(s) is True
        assert elaboration._has_api_key(s) is True
        assert autocode_catch_up.cloud_ready(s) is True
        assert chat_lens.has_usable_provider(s) == (True, "")


class TestAutoCodeRefusal:
    """The SPA turns ``reason`` into its sentence; the wrong reason is the wrong field."""

    def _refusal(self, settings: BristlenoseSettings) -> RefusalError:
        from bristlenose.server.routes.autocode import require_provider_ready

        with pytest.raises(RefusalError) as info:
            require_provider_ready(settings)
        return info.value

    def test_a_keyed_azure_without_endpoint_is_not_called_a_missing_key(self) -> None:
        err = self._refusal(_azure(azure_endpoint=""))
        assert err.reason is RefusalReason.PROVIDER_AMBIGUOUS

    def test_an_azure_without_a_key_is_a_missing_key(self) -> None:
        err = self._refusal(_azure(azure_api_key=""))
        assert err.reason is RefusalReason.NO_API_KEY

    def test_a_complete_azure_is_not_refused(self) -> None:
        from bristlenose.server.routes.autocode import require_provider_ready

        require_provider_ready(_azure())
