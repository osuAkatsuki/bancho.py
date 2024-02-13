from __future__ import annotations

import pytest

import app.packets


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"\x05\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"\x05\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_user_id(test_input, expected):
    assert app.packets.login_reply(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            {
                "sender": "cmyui",
                "msg": "woah woah crazy!!",
                "recipient": "jacobian",
                "sender_id": 32,
            },
            b"\x07\x00\x00(\x00\x00\x00\x0b\x05cmyui\x0b\x11woah woah crazy!!\x0b\x08jacobian \x00\x00\x00",
        ),
        (
            {
                "sender": "",
                "msg": "",
                "recipient": "",
                "sender_id": 0,
            },
            b"\x07\x00\x00\x07\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
        ),
    ],
)
def test_write_send_message(test_input, expected):
    assert app.packets.send_message(**test_input) == expected


def test_write_pong():
    assert app.packets.pong() == b"\x08\x00\x00\x00\x00\x00\x00"


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            {"old": "cmyui", "new": "abcgamer321"},
            b"\t\x00\x00\x16\x00\x00\x00\x0b\x14cmyui>>>>abcgamer321",
        ),
        (
            {"old": "", "new": ""},
            b"\t\x00\x00\x06\x00\x00\x00\x0b\x04>>>>",
        ),
    ],
)
def test_write_change_username(test_input, expected):
    assert app.packets.change_username(**test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            {
                "user_id": 1001,
                "action": 2,  # playing
                "info_text": "gaming",  # TODO: get a realistic one
                "map_md5": "60b725f10c9c85c70d97880dfe8191b3",
                "mods": 64,
                "mode": 0,
                "map_id": 1723723,
                "ranked_score": 1_238_917_112,
                "accuracy": 92.32,
                "plays": 3821,
                "total_score": 3_812_428_392,
                "global_rank": 42,
                "pp": 8291,
            },
            b"\x0b\x00\x00V\x00\x00\x00\xe9\x03\x00\x00\x02\x0b\x06gaming\x0b 60b725f10c9c85c70d97880dfe8191b3@\x00\x00\x00\x00KM\x1a\x00\xf8_\xd8I\x00\x00\x00\x00\xd6Vl?\xed\x0e\x00\x00h\n=\xe3\x00\x00\x00\x00*\x00\x00\x00c ",
        ),
        (
            {
                "user_id": 0,
                "action": 0,
                "info_text": "",
                "map_md5": "",  # TODO: can this even be empty
                "mods": 0,
                "mode": 0,
                "map_id": 0,
                "ranked_score": 0,
                "accuracy": 0.0,
                "plays": 0,
                "total_score": 0,
                "global_rank": 0,
                "pp": 0,
            },
            b"\x0b\x00\x00.\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
        ),
    ],
)
def test_write_user_stats(test_input, expected):
    assert app.packets._user_stats(**test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"\x0c\x00\x00\x05\x00\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"\x0c\x00\x00\x05\x00\x00\x00\xff\xff\xff\x7f\x00"),
    ],
)
def test_write_logout(test_input, expected):
    assert app.packets.logout(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"\x0d\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"\x0d\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_spectator_joined(test_input, expected):
    assert app.packets.spectator_joined(test_input) == expected
    ...


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"\x0e\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"\x0e\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_spectator_left(test_input, expected):
    assert app.packets.spectator_left(test_input) == expected


@pytest.mark.xfail(reason="need to implement proper writing")
@pytest.mark.parametrize(("test_input", "expected"), [({}, b"")])
def test_write_spectate_frames(test_input, expected):
    assert app.packets.spectate_frames(test_input) == expected


def test_write_version_update():
    assert app.packets.version_update() == b"\x13\x00\x00\x00\x00\x00\x00"


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"\x16\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"\x16\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_spectator_cant_spectate(test_input, expected):
    assert app.packets.spectator_cant_spectate(test_input) == expected


def test_write_get_attention():
    assert app.packets.get_attention() == b"\x17\x00\x00\x00\x00\x00\x00"


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ("waowww", b"\x18\x00\x00\x08\x00\x00\x00\x0b\x06waowww"),
        ("", b"\x18\x00\x00\x01\x00\x00\x00\x00"),
    ],
)
def test_write_notification(test_input, expected):
    assert app.packets.notification(test_input) == expected


@pytest.mark.xfail(reason="need to remove bancho.py match object")
@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ({"m": None, "send_pw": False}, b""),
        ({"m": None, "send_pw": True}, b""),
    ],
)
def test_write_update_match(test_input, expected):
    assert app.packets.update_match(test_input) == expected


@pytest.mark.xfail(reason="need to remove bancho.py match object")
@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ({}, b""),
        ({}, b""),
    ],
)
def test_write_new_match(test_input, expected):
    assert app.packets.new_match(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"\x1c\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"\x1c\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_dispose_match(test_input, expected):
    assert app.packets.dispose_match(test_input) == expected


def test_write_toggle_block_non_friend_pm():
    assert app.packets.toggle_block_non_friend_dm() == b'"\x00\x00\x00\x00\x00\x00'


@pytest.mark.xfail(reason="need to remove bancho.py match object")
@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ({}, b""),
        ({}, b""),
    ],
)
def test_write_match_join_success(test_input, expected):
    assert app.packets.match_join_success(test_input) == expected


def test_write_match_join_fail():
    assert app.packets.match_join_fail() == b"%\x00\x00\x00\x00\x00\x00"


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"*\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"*\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_fellow_spectator_joined(test_input, expected):
    assert app.packets.fellow_spectator_joined(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"+\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"+\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_fellow_spectator_left(test_input, expected):
    assert app.packets.fellow_spectator_left(test_input) == expected


@pytest.mark.xfail(reason="need to remove bancho.py match object")
@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ({}, b""),
        ({}, b""),
    ],
)
def test_write_match_start(test_input, expected):
    assert app.packets.match_start(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            app.packets.ScoreFrame(
                time=38242,  # TODO: check if realistic
                id=28,  # TODO: check if realistic
                num300=320,
                num100=48,
                num50=2,
                num_geki=32,
                num_katu=8,
                num_miss=3,
                total_score=492_392,
                current_combo=39,
                max_combo=122,
                perfect=False,
                current_hp=245,  # TODO: check if realistic
                tag_byte=0,
                score_v2=False,
                # NOTE: this stuff isn't written
                # combo_portion=0.0,
                # bonus_portion=0.0,
            ),
            b"0\x00\x00\x1d\x00\x00\x00b\x95\x00\x00\x1c@\x010\x00\x02\x00 \x00\x08\x00\x03\x00h\x83\x07\x00z\x00'\x00\x00\xf5\x00\x00",
        ),
        (
            app.packets.ScoreFrame(
                time=0,
                id=0,
                num300=0,
                num100=0,
                num50=0,
                num_geki=0,
                num_katu=0,
                num_miss=0,
                total_score=0,
                current_combo=0,
                max_combo=0,
                perfect=False,
                current_hp=0,
                tag_byte=0,
                score_v2=False,
                combo_portion=0.0,
                bonus_portion=0.0,
            ),
            b"0\x00\x00\x1d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
        ),
    ],
)
def test_write_match_score_update(test_input, expected):
    assert app.packets.match_score_update(test_input) == expected


def test_write_match_transfer_host():
    assert app.packets.match_transfer_host() == b"2\x00\x00\x00\x00\x00\x00"


def test_write_match_all_players_loaded():
    assert app.packets.match_all_players_loaded() == b"5\x00\x00\x00\x00\x00\x00"


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"9\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"9\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_match_player_failed(test_input, expected):
    assert app.packets.match_player_failed(test_input) == expected


def test_write_match_complete():
    assert app.packets.match_complete() == b":\x00\x00\x00\x00\x00\x00"


def test_write_match_skip():
    assert app.packets.match_skip() == b"=\x00\x00\x00\x00\x00\x00"


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ("#osu", b"@\x00\x00\x06\x00\x00\x00\x0b\x04#osu"),
        ("", b"@\x00\x00\x01\x00\x00\x00\x00"),
    ],
)
def test_write_channel_join(test_input, expected):
    assert app.packets.channel_join(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            ("#osu", "le topique", 123),
            b"A\x00\x00\x14\x00\x00\x00\x0b\x04#osu\x0b\nle topique{\x00",
        ),
        (("", "", 0), b"A\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
    ],
)
def test_write_channel_info(test_input, expected):
    assert app.packets.channel_info(*test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ("#osu", b"B\x00\x00\x06\x00\x00\x00\x0b\x04#osu"),
        ("", b"B\x00\x00\x01\x00\x00\x00\x00"),
    ],
)
def test_write_channel_kick(test_input, expected):
    assert app.packets.channel_kick(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            ("#osu", "le topique", 123),
            b"C\x00\x00\x14\x00\x00\x00\x0b\x04#osu\x0b\nle topique{\x00",
        ),
        (("", "", 0), b"C\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
    ],
)
def test_write_channel_auto_join(test_input, expected):
    assert app.packets.channel_auto_join(*test_input) == expected


# TODO: test_write_beatmap_info_reply? it's disabled in
# app.packets but perhaps for completion i can keep it in


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"G\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"G\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_bancho_privileges(test_input, expected):
    assert app.packets.bancho_privileges(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            [1, 4, 1001],
            b"H\x00\x00\x0e\x00\x00\x00\x03\x00\x01\x00\x00\x00\x04\x00\x00\x00\xe9\x03\x00\x00",
        ),
        (
            [],
            b"H\x00\x00\x02\x00\x00\x00\x00\x00",
        ),
    ],
)
def test_write_friends_list(test_input, expected):
    assert app.packets.friends_list(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"K\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"K\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_protocol_version(test_input, expected):
    assert app.packets.protocol_version(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            ("https://icon-url.ca/a.png", "https://onclick-url.ca/a.png"),
            b"L\x00\x008\x00\x00\x00\x0b6https://icon-url.ca/a.png|https://onclick-url.ca/a.png",
        ),
        (
            ("", ""),
            b"L\x00\x00\x03\x00\x00\x00\x0b\x01|",
        ),
    ],
)
def test_write_main_menu_icon(test_input, expected):
    assert app.packets.main_menu_icon(*test_input) == expected


def test_write_monitor():
    assert app.packets.monitor() == b"P\x00\x00\x00\x00\x00\x00"


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"Q\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"Q\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_match_player_skipped(test_input, expected):
    assert app.packets.match_player_skipped(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            {
                "user_id": 1001,
                "name": "cmyui",
                "utc_offset": -5,
                "country_code": 38,
                "bancho_privileges": 31,  # owner|dev|supporter|mod|player
                "mode": 0,
                "longitude": 43.768,
                "latitude": -79.522,
                "global_rank": 42,
            },
            b"S\x00\x00\x1a\x00\x00\x00\xe9\x03\x00\x00\x0b\x05cmyui\x13&\x1fo\x12/BD\x0b\x9f\xc2*\x00\x00\x00",
        ),
        (
            {
                "user_id": 0,
                "name": "",
                "utc_offset": 0,
                "country_code": 0,
                "bancho_privileges": 0,
                "mode": 0,
                "longitude": 0.0,
                "latitude": 0.0,
                "global_rank": 0,
            },
            b"S\x00\x00\x14\x00\x00\x00\x00\x00\x00\x00\x00\x18\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
        ),
    ],
)
def test_write_user_presence(test_input, expected):
    assert app.packets._user_presence(**test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"V\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"V\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_restart_server(test_input, expected):
    assert app.packets.restart_server(test_input) == expected


@pytest.mark.xfail(reason="need to remove bancho.py match object")
@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ({"p": None, "t_name": "cover"}, b""),
        ({"p": None, "t_name": "cover"}, b""),
    ],
)
def test_write_match_invite(test_input, expected):
    assert app.packets.match_invite(**test_input) == expected


def test_channel_info_end():
    assert app.packets.channel_info_end() == b"Y\x00\x00\x00\x00\x00\x00"


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ("newpassword", b"[\x00\x00\x0d\x00\x00\x00\x0b\x0bnewpassword"),
        ("", b"[\x00\x00\x01\x00\x00\x00\x00"),
    ],
)
def test_write_match_change_password(test_input, expected):
    assert app.packets.match_change_password(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"\\\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"\\\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_silence_end(test_input, expected):
    assert app.packets.silence_end(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"^\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"^\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_user_silenced(test_input, expected):
    assert app.packets.user_silenced(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"_\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"_\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_user_presence_single(test_input, expected):
    assert app.packets.user_presence_single(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            [1, 4, 1001],
            b"`\x00\x00\x0e\x00\x00\x00\x03\x00\x01\x00\x00\x00\x04\x00\x00\x00\xe9\x03\x00\x00",
        ),
        (
            [],
            b"`\x00\x00\x02\x00\x00\x00\x00\x00",
        ),
    ],
)
def test_write_user_presence_bundle(test_input, expected):
    assert app.packets.user_presence_bundle(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ("cover", b"d\x00\x00\r\x00\x00\x00\x00\x00\x0b\x05cover\x00\x00\x00\x00"),
        ("", b"d\x00\x00\x07\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"),
    ],
)
def test_write_user_dm_blocked(test_input, expected):
    assert app.packets.user_dm_blocked(test_input) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ("cover", b"e\x00\x00\r\x00\x00\x00\x00\x00\x0b\x05cover\x00\x00\x00\x00"),
        ("", b"e\x00\x00\x07\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"),
    ],
)
def test_write_target_silenced(test_input, expected):
    assert app.packets.target_silenced(test_input) == expected


def test_write_version_update_forced():
    assert app.packets.version_update_forced() == b"f\x00\x00\x00\x00\x00\x00"


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, b"g\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"),
        (2_147_483_647, b"g\x00\x00\x04\x00\x00\x00\xff\xff\xff\x7f"),
    ],
)
def test_write_switch_server(test_input, expected):
    assert app.packets.switch_server(test_input) == expected


def test_write_account_restricted():
    assert app.packets.account_restricted() == b"h\x00\x00\x00\x00\x00\x00"


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ("yoyoo rip rtx", b"i\x00\x00\x0f\x00\x00\x00\x0b\ryoyoo rip rtx"),
        ("", b"i\x00\x00\x01\x00\x00\x00\x00"),
    ],
)
def test_write_rtx(test_input, expected):
    assert app.packets.rtx(test_input) == expected


def test_write_match_abort():
    assert app.packets.match_abort() == b"j\x00\x00\x00\x00\x00\x00"


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            "61.91.139.24",
            b"k\x00\x00\x0e\x00\x00\x00\x0b\x0c61.91.139.24",
        ),
        ("", b"k\x00\x00\x01\x00\x00\x00\x00"),
    ],
)
def test_write_switch_tournament_server(test_input, expected):
    assert app.packets.switch_tournament_server(test_input) == expected
