from unittest.mock import Mock

from costsage.notifier import get_slack_webhook_url


def _mock_secrets_client(secret_string: str):
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": secret_string}
    return client


def test_get_slack_webhook_url_from_raw_secret_string():
    secret = "https://hooks.slack.com/services/T000/B000/RAW"
    client = _mock_secrets_client(secret)

    result = get_slack_webhook_url(client, "costsage/prod/slack-webhook")

    assert result == secret


def test_get_slack_webhook_url_from_json_secret_string():
    client = _mock_secrets_client('{"webhook_url":"https://hooks.slack.com/services/T000/B000/JSON"}')

    result = get_slack_webhook_url(client, "costsage/prod/slack-webhook")

    assert result == "https://hooks.slack.com/services/T000/B000/JSON"


def test_get_slack_webhook_url_from_escaped_json_secret_string():
    client = _mock_secrets_client('"{\\"webhook_url\\":\\"https://hooks.slack.com/services/T000/B000/ESCAPED\\"}"')

    result = get_slack_webhook_url(client, "costsage/prod/slack-webhook")

    assert result == "https://hooks.slack.com/services/T000/B000/ESCAPED"


def test_get_slack_webhook_url_extracts_url_from_malformed_payload():
    client = _mock_secrets_client('{webhook_url:https://hooks.slack.com/services/T000/B000/BROKEN}')

    result = get_slack_webhook_url(client, "costsage/prod/slack-webhook")

    assert result == "https://hooks.slack.com/services/T000/B000/BROKEN"
