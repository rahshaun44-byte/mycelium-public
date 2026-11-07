import pytest

from mcp_layer.qf_bot.context_store import ContentPolicyError, _validate_content


def test_context_policy_rejects_restricted_classification():
    with pytest.raises(ContentPolicyError, match="restricted"):
        _validate_content("retain this", "RESTRICTED")


@pytest.mark.parametrize(
    "content",
    [
        "password = 'example-password-value'",
        "-----BEGIN RSA PRIVATE KEY-----",
        "ghp_abcdefghijklmnopqrstuvwxyz012345",
    ],
)
def test_context_policy_rejects_obvious_credentials(content):
    with pytest.raises(ContentPolicyError, match="credential"):
        _validate_content(content, "INTERNAL")


def test_context_policy_allows_ordinary_project_notes():
    _validate_content("ATHENA should inspect the parser tests next.", "INTERNAL")
