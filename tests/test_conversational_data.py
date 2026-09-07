"""Tests for ConversationalDataDriver request payloads."""

import asyncio
from unittest import mock

from inmydata.ConversationalData import ConversationalDataDriver


def test_ai_question_payload_includes_optional_user_id():
    with mock.patch("inmydata.ConversationalData.HubConnectionBuilder"):
        driver = ConversationalDataDriver(
            tenant="test", server="example.com", api_key="test-key", user_id="user-123"
        )

    captured = {}

    async def post_request(url, data):
        captured["data"] = data
        return {"answer": "Answer", "answerDataJson": "{}", "subject": "Sales"}

    driver._ConversationalDataDriver__post_request = post_request
    asyncio.run(driver.get_answer("How are sales?", subject="Sales"))

    assert captured["data"]["UserId"] == "user-123"


def test_ai_question_payload_omits_user_id_by_default():
    with mock.patch("inmydata.ConversationalData.HubConnectionBuilder"):
        driver = ConversationalDataDriver(tenant="test", server="example.com", api_key="test-key")

    captured = {}

    async def post_request(url, data):
        captured["data"] = data
        return {"answer": "Answer", "answerDataJson": "{}", "subject": "Sales"}

    driver._ConversationalDataDriver__post_request = post_request
    asyncio.run(driver.get_answer("How are sales?", subject="Sales"))

    assert "UserId" not in captured["data"]