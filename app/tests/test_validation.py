from __future__ import annotations

import random

import pytest

import app.settings
from app import validation

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("setup_app")]


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            # passing case
            {
                "player_name": "test_user",
                "email": "some-tesT_email@gmail.com",
                "pw_plaintext": "Abc123#@!real",
            },
            {},
        ),
        ## username validation
        (
            # username too short
            {
                "player_name": "a",
                "email": "some-tesT_email@gmail.com",
                "pw_plaintext": "Abc123#@!real",
            },
            {"username": ["Username must be 2-15 characters in length."]},
        ),
        (
            # username too long
            {
                "player_name": "a" * 16,
                "email": "some-tesT_email@gmail.com",
                "pw_plaintext": "Abc123#@!real",
            },
            {"username": ["Username must be 2-15 characters in length."]},
        ),
        (
            # username contains "_" and " "
            {
                "player_name": "1234_ ",
                "email": "some-tesT_email@gmail.com",
                "pw_plaintext": "Abc123#@!real",
            },
            {"username": ['Username may contain "_" and " ", but not both.']},
        ),
        (
            # username is in disallowed list
            {
                "player_name": random.choice(app.settings.DISALLOWED_NAMES),
                "email": "some-tesT_email@gmail.com",
                "pw_plaintext": "Abc123#@!real",
            },
            {"username": ["Username disallowed."]},
        ),
        (
            # username is taken by another player
            {
                "player_name": "BanchoBot",
                "email": "some-tesT_email@gmail.com",
                "pw_plaintext": "Abc123#@!real",
            },
            {"username": ["Username already taken by another player."]},
        ),
        ## email validation
        (
            # email syntax is invalid (test #1)
            {
                "player_name": "test_user",
                "email": "some-tesT_email",
                "pw_plaintext": "Abc123#@!real",
            },
            {"user_email": ["Email syntax invalid."]},
        ),
        (
            # email syntax is invalid (test #2)
            {
                "player_name": "test_user",
                "email": "some-tesT_email@gmail",
                "pw_plaintext": "Abc123#@!real",
            },
            {"user_email": ["Email syntax invalid."]},
        ),
        (
            # email syntax is invalid (test #3)
            {
                "player_name": "test_user",
                "email": "@gmail.com",
                "pw_plaintext": "Abc123#@!real",
            },
            {"user_email": ["Email syntax invalid."]},
        ),
        # TODO: add more syntax validation tests?
        (
            # email is taken by another player
            {
                "player_name": "test_user",
                "email": "bot@akatsuki.pw",
                "pw_plaintext": "Abc123#@!real",
            },
            {"user_email": ["Email already taken by another player."]},
        ),
        ## password validation
        (
            # password is too short
            {
                "player_name": "test_user",
                "email": "some-tesT_email@gmail.com",
                "pw_plaintext": "1234567",
            },
            {"password": ["Password must be 8-72 characters in length."]},
        ),
        (
            # password is too long
            {
                "player_name": "test_user",
                "email": "some-tesT_email@gmail.com",
                "pw_plaintext": ("1234567890" * 7) + "aaa",  # 73 chars
            },
            {"password": ["Password must be 8-72 characters in length."]},
        ),
        (
            # password doesn't have enough uniqueness
            {
                "player_name": "test_user",
                "email": "some-tesT_email@gmail.com",
                "pw_plaintext": "a" * 16,
            },
            {"password": ["Password must have more than 3 unique characters."]},
        ),
    ],
)
async def test_registration_validation(test_input, expected):
    assert (
        await validation.osu_registration(
            **test_input,
            check_breaches=False,
        )
        == expected
    )
