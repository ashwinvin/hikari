#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright © Nekoka.tt 2019
#
# This file is part of Hikari.
#
# Hikari is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Hikari is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Hikari. If not, see <https://www.gnu.org/licenses/>.
from unittest import mock

import pytest

from hikari.core.model import emoji
from hikari.core.model import model_cache


@pytest.fixture
def mock_state():
    return mock.MagicMock(spec_set=model_cache.AbstractModelCache)


@pytest.fixture
def unicode_emoji_payload():
    return {"name": "\N{OK HAND SIGN}"}


@pytest.fixture
def unknown_emoji_payload():
    return {"name": "asshat123", "id": "100000000001110010"}


@pytest.fixture
def user_payload():
    return {
        "username": "Luigi",
        "discriminator": "0002",
        "id": "96008815106887111",
        "avatar": "5500909a3274e1812beb4e8de6631111",
    }


@pytest.fixture
def guild_emoji_payload(user_payload):
    return {
        "id": "41771983429993937",
        "name": "LUL",
        "roles": ["41771983429993000", "41771983429993111"],
        "user": user_payload,
        "require_colons": True,
        "managed": False,
        "animated": False,
    }


@pytest.mark.model
def test_UnicodeEmoji___init__(unicode_emoji_payload):
    assert emoji.UnicodeEmoji(unicode_emoji_payload).value == "\N{OK HAND SIGN}"


@pytest.mark.model
def test_UnicodeEmoji___eq__(unicode_emoji_payload):
    assert emoji.UnicodeEmoji(unicode_emoji_payload) == "\N{OK HAND SIGN}"


@pytest.mark.model
def test_UnicodeEmoji___ne__(unicode_emoji_payload):
    assert emoji.UnicodeEmoji(unicode_emoji_payload) != "\N{AUBERGINE}"


@pytest.mark.model
def test_UnicodeEmoji___str__(unicode_emoji_payload):
    assert str(emoji.UnicodeEmoji(unicode_emoji_payload)) == "\N{OK HAND SIGN}"


@pytest.mark.model
def test_UnknownEmoji___init__(unknown_emoji_payload):
    e = emoji.UnknownEmoji(unknown_emoji_payload)
    assert e.id == 100000000001110010
    assert e.name == "asshat123"


@pytest.mark.model
def test_GuildEmoji___init__(mock_state, guild_emoji_payload, user_payload):
    user = mock.MagicMock()
    mock_state.parse_user = mock.MagicMock(return_value=user)
    e = emoji.GuildEmoji(mock_state, guild_emoji_payload, 98765)

    assert e.id == 41771983429993937
    assert e.name == "LUL"
    assert e._role_ids == [41771983429993000, 41771983429993111]
    assert e.user is user
    assert e.require_colons is True
    assert e.managed is False
    assert e.animated is False
    assert e._guild_id == 98765
    mock_state.parse_user.assert_called_with(user_payload)


@pytest.mark.model
def test_emoji_from_dict_with_unicode_emoji(mock_state, unicode_emoji_payload):
    assert isinstance(emoji.emoji_from_dict(mock_state, unicode_emoji_payload), emoji.UnicodeEmoji)


@pytest.mark.model
def test_emoji_from_dict_with_unknown_emoji(mock_state, unknown_emoji_payload):
    e = emoji.emoji_from_dict(mock_state, unknown_emoji_payload)
    assert isinstance(e, emoji.UnknownEmoji)
    assert not isinstance(e, emoji.GuildEmoji)


@pytest.mark.model
def test_emoji_from_dict_with_guild_emoji(mock_state, guild_emoji_payload):
    assert isinstance(emoji.emoji_from_dict(mock_state, guild_emoji_payload), emoji.GuildEmoji)