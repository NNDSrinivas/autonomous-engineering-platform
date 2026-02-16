import logging

from backend.services.navi_brain import NaviBrain


def _sample_payload(secret: str) -> dict:
    return {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": "system instructions"},
            {"role": "user", "content": f"token={secret}"},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "arguments": {"cmd": f"echo {secret}"},
                },
            }
        ],
    }


def test_openai_request_debug_redacts_payload_content(caplog) -> None:
    secret = "sk-test-should-not-leak"
    brain = NaviBrain(provider="openai", model="gpt-4o", api_key="test")
    payload = _sample_payload(secret)

    with caplog.at_level(logging.INFO, logger="backend.services.navi_brain"):
        brain._log_openai_request_debug(
            model="gpt-4o",
            endpoint="https://api.openai.com/v1/chat/completions",
            stream=False,
            payload=payload,
        )

    assert secret not in caplog.text
    assert "payload_meta" in caplog.text


def test_openai_400_debug_redacts_error_message(caplog) -> None:
    secret = "sk-test-should-not-leak"
    brain = NaviBrain(provider="openai", model="gpt-4o", api_key="test")
    payload = _sample_payload(secret)
    error_body = {
        "error": {
            "type": "invalid_request_error",
            "code": "invalid_model",
            "message": f"invalid token {secret}",
        }
    }

    with caplog.at_level(logging.ERROR, logger="backend.services.navi_brain"):
        brain._log_openai_400_debug(
            model="gpt-4o",
            endpoint="https://api.openai.com/v1/chat/completions",
            stream=True,
            payload=payload,
            error_body=error_body,
        )

    assert secret not in caplog.text
    assert "error_summary" in caplog.text
