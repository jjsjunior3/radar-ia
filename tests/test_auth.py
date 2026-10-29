import httpx
import pytest
from radar_ia.auth import check_openrouter_auth


def test_auth_uses_metadata_endpoint_without_model_request():
    def handler(request):
        assert str(request.url) == "https://openrouter.ai/api/v1/key"
        assert request.method == "GET"
        assert request.headers["authorization"] == "Bearer fake-key"
        return httpx.Response(200, json={"data": {}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        check_openrouter_auth("fake-key", client)


def test_auth_error_does_not_expose_response_or_key():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401, text="sensitive-response"))) as client:
        with pytest.raises(ValueError) as error:
            check_openrouter_auth("fake-secret", client)
        assert "401" in str(error.value)
        assert "fake-secret" not in str(error.value)
        assert "sensitive-response" not in str(error.value)
