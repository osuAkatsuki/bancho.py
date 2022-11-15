"""osu!trainer support for bancho.py

featuring some reallllly quick and dirty code so i could avoid writing
a .osu file writer. probably would have been easier in hindsight lmaoo
"""
from __future__ import annotations

import random
import re

# range that osu!trainer beatmaps will be stored at
# NOTE that they're also marked with server='private' in sql
MIN_MAP_ID = 1_000_000_000
MAX_MAP_ID = 2_000_000_000

# osu! train shenanigans

OSU_TRAINER_SPEED = re.compile(r"(?P<speed>\d(?:\.\d{1,2})?)x \((?P<bpm>\d+)bpm\)")
OSU_TRAINER_HP = re.compile(r"HP(?P<hp>(?:11|10|\d)(?:\.\d{1,2})?)")
OSU_TRAINER_CS = re.compile(r"CS(?P<cs>(?:11|10|\d)(?:\.\d{1,2})?)")
OSU_TRAINER_AR = re.compile(r"AR(?P<ar>(?:11|10|\d)(?:\.\d{1,2})?)")
OSU_TRAINER_OD = re.compile(r"OD(?P<od>(?:11|10|\d)(?:\.\d{1,2})?)")


async def get_unused_osu_map_id() -> int:
    import app.state.services

    new_id = 0
    map_exists = True
    while map_exists:
        new_id = random.randint(MIN_MAP_ID, MAX_MAP_ID)
        map_exists = await app.state.services.database.fetch_one(
            "SELECT 1 FROM maps WHERE id = :id",
            {"id": new_id},
        )
    return new_id


def split_version_from_edits(full_version: str) -> tuple[str, dict[str, str]]:
    version = full_version

    # fmt: off
    edits: dict[str, str] = {}
    speed_edits = [match.groupdict() for match in OSU_TRAINER_SPEED.finditer(version)]
    if speed_edits:
        edits.update(speed_edits[-1])
    hp_edits = [match.groupdict() for match in OSU_TRAINER_HP.finditer(version)]
    if hp_edits:
        edits.update(hp_edits[-1])
    cs_edits = [match.groupdict() for match in OSU_TRAINER_CS.finditer(version)]
    if cs_edits:
        edits.update(cs_edits[-1])
    ar_edits = [match.groupdict() for match in OSU_TRAINER_AR.finditer(version)]
    if ar_edits:
        edits.update(ar_edits[-1])
    od_edits = [match.groupdict() for match in OSU_TRAINER_OD.finditer(version)]
    if od_edits:
        edits.update(od_edits[-1])

    # keeping the ordering of these asserted
    if 'od' in edits:
        new_version = version.removesuffix(f" OD{edits['od']}")
        assert new_version != version
        version = new_version
    if 'ar' in edits:
        new_version = version.removesuffix(f" AR{edits['ar']}")
        assert new_version != version
        version = new_version
    if 'cs' in edits:
        new_version = version.removesuffix(f" CS{edits['cs']}")
        assert new_version != version
        version = new_version
    if 'hp' in edits:
        new_version = version.removesuffix(f" HP{edits['hp']}")
        assert new_version != version
        version = new_version
    if 'speed' in edits:
        new_version = version.removesuffix(f" {edits['speed']}x ({edits['bpm']}bpm)")
        assert new_version != version
        version = new_version
    # fmt: on

    return version, edits


# ar scaling tools


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min(value, max_value), min_value)


def ar_to_ms(ar: float):
    if ar <= 5:
        return 1800.0 - ar * 120.0
    else:
        return 1200.0 - (ar - 5) * 150.0


def ms_to_ar(ms: float) -> float:
    smallest_diff = 100_000.0
    for ar in range(110):
        new_diff = abs(ar_to_ms(ar / 10) - ms)
        if new_diff < smallest_diff:
            smallest_diff = new_diff
        else:
            return (ar - 1) / 10.0

    return 11


def calculate_multiplied_ar(ar: float, multiplier: float) -> float:
    return ms_to_ar(ar_to_ms(ar) / multiplier)


# od scaling tools


def od_to_ms(od: float) -> float:
    return -6.0 * od + 79.5


def ms_to_od(ms: float) -> float:
    return (79.5 - ms) / 6.0


def calculate_multiplied_od(od: float, multiplier: float) -> float:
    # TODO: ? https://github.com/FunOrange/osu-trainer/blob/e37042ff00d6d62a98af7e68b7652d1930ee05e2/osu-trainer/DifficultyCalculator.cs#L60
    return ms_to_od(od_to_ms(od) / multiplier)


def create_edited_osu_file(
    original_version: str,
    new_version: str,
    new_beatmap_id: int,
    current_osu_file_content: str,
    edits: dict[str, str],
) -> str:
    # i dont want to write a reader & writer
    if not edits:
        raise Exception("why u calling me with no edits")

    osu_file_content = current_osu_file_content

    print("creating new file contents")
    print("original_version", original_version)
    print("new_version", new_version)
    print("edits", edits)

    # TODO: if difficulty settings >10, osu! trainer expects the
    # player to use DT, so we need to adjust timing for that

    if "od" in edits:
        osu_file_content = re.sub(
            pattern=r"\nOverallDifficulty: *(?:11|10|\d(?:)?)\n",
            repl=f"\nOverallDifficulty: {edits['od']}\n",
            string=osu_file_content,
            count=1,
        )
    if "ar" in edits:
        osu_file_content = re.sub(
            pattern=r"\nApproachRate: *(?:11|10|\d(?:\.\d{1,2})?)\n",
            repl=f"\nApproachRate: {edits['ar']}\n",
            string=osu_file_content,
            count=1,
        )
    if "cs" in edits:
        osu_file_content = re.sub(
            pattern=r"\nCircleSize: *(?:11|10|\d(?:\.\d{1,2})?)\n",
            repl=f"\nCircleSize: {edits['cs']}\n",
            string=osu_file_content,
            count=1,
        )
    if "hp" in edits:
        osu_file_content = re.sub(
            pattern=r"\nHPDrainRate: *(?:11|10|\d(?:\.\d{1,2})?)\n",
            repl=f"\nHPDrainRate: {edits['hp']}\n",
            string=osu_file_content,
            count=1,
        )
    if "speed" in edits:
        rate_change = float(edits["speed"])

        if "od" not in edits:
            # they editing speed but not pinning od - scale it with speed
            start_idx = osu_file_content.find("\nOverallDifficulty:") + len(
                "\nOverallDifficulty:",
            )
            end_idx = osu_file_content.find("\n", start_idx)
            current_od = float(osu_file_content[start_idx:end_idx].lstrip())

            osu_file_content = re.sub(
                # XXX: not going to search for exact value since i've seen
                # osu/osu trainer do some inconsistency w/ float precision
                pattern=r"\nOverallDifficulty: *(?:11|10|\d(?:\.\d{1,2})?)\n",
                repl=f"\nOverallDifficulty:{calculate_multiplied_od(current_od, rate_change):.1f}\n",
                string=osu_file_content,
                count=1,
            )

        if "ar" not in edits:
            # they editing speed but not pinning ar - scale it with speed
            start_idx = osu_file_content.find("\nApproachRate:") + len(
                "\nApproachRate:",
            )
            end_idx = osu_file_content.find("\n", start_idx)
            current_ar = float(osu_file_content[start_idx:end_idx].lstrip())

            osu_file_content = re.sub(
                # XXX: not going to search for exact value since i've seen
                # osu/osu trainer do some inconsistency w/ float precision
                pattern=r"\nApproachRate: *(?:11|10|\d(?:\.\d{1,2})?)\n",
                repl=f"\nApproachRate:{calculate_multiplied_ar(current_ar, rate_change):.1f}\n",
                string=osu_file_content,
                count=1,
            )

        # update audio file name
        osu_file_content = re.sub(
            pattern=rf"\nAudioFilename: (.+)\.mp3\n",
            # TODO: there seems to be a difference in rounding here with
            # osu! trainer. this is important to get right as the client
            # uses this to reference the audio file.
            # getting it wrong = no audio
            repl=rf"\nAudioFilename: \1 {float(edits['speed']):.3f}x.mp3\n",
            string=osu_file_content,
            count=1,
        )

        # https://github.com/FunOrange/FsBeatmapParser/blob/58986c6b1d6f9d402d4818b0b2f5f6479eb5d91f/FsBeatmap.fs#L163-L200
        # https://github.com/FunOrange/osu-trainer/blob/master/osu-trainer/BeatmapEditor.cs#L818-L874

        # rewrite timing points
        osu_file_lines = osu_file_content.splitlines()
        in_timing_points = False
        for i, line in enumerate(osu_file_lines):
            if line == "[TimingPoints]":
                in_timing_points = True
                continue

            if not in_timing_points:
                continue

            if not line:
                # wait til [
                continue

            if line.startswith("["):
                # k we're done fr
                break

            # rewrite timing point
            split = line.split(",", maxsplit=7)
            assert len(split) == 8, split
            osu_file_lines[i] = ",".join(
                [
                    # before: 28,285.71428571428583333333333333,4,1,1,100,1,0
                    # after:  34,342.857142857143,4,1,1,100,1,0
                    str(int(float(split[0]) / rate_change)),
                    str(float(split[1]) / rate_change) if split[6] == "1" else split[1],
                    # f"{float(split[1]) / rate_change:.12f}",
                    split[2],  # TODO: tiny differences on this vs. osu trainer?
                    split[3],
                    split[4],
                    split[5],
                    split[6],
                    split[7],
                ],
            )

        osu_file_content = "\n".join(osu_file_lines)

        # rewrite hit objects
        osu_file_lines = osu_file_content.splitlines()
        in_hit_objects = False
        for i, line in enumerate(osu_file_lines):
            if line == "[HitObjects]":
                in_hit_objects = True
                continue

            if not in_hit_objects:
                continue

            if not line:
                # wait til [
                continue

            if line.startswith("["):
                # k we're done fr
                break

            # rewrite hit object
            split = line.split(",", maxsplit=5)
            assert len(split) == 6, split  # TODO: this is 5 on mythologia's end
            osu_file_lines[i] = ",".join(
                [
                    # before: 0,0,0,0,0,0:0:0:0:
                    # after:  0,0,0,0,0,0:0:0:0:
                    split[0],
                    split[1],
                    str(int(int(split[2]) / rate_change)),
                    split[3],
                    split[4],
                    split[5],
                ],
            )

        osu_file_content = "\n".join(osu_file_lines)

        # rewrite break periods
        osu_file_lines = osu_file_content.splitlines()
        in_break_periods = False
        for i, line in enumerate(osu_file_lines):
            if line == "//Break Periods":
                in_break_periods = True
                continue

            if not in_break_periods:
                continue

            if not line:
                # wait til //
                continue

            if line.startswith("//"):
                # k we're done fr
                break

            # rewrite break period
            split = line.split(",", maxsplit=2)
            assert len(split) == 3, split
            osu_file_lines[i] = ",".join(
                [
                    # before: 2,89376,99548
                    # after:  2,74480,82956
                    split[0],
                    str(int(int(split[1]) / rate_change)),
                    str(int(int(split[2]) / rate_change)),
                ],
            )

        osu_file_content = "\n".join(osu_file_lines)

        # update preview time
        osu_file_content = re.sub(
            pattern=rf"\nPreviewTime: (\d+)\n",
            repl=lambda match: f"\nPreviewTime: {int(int(match.group(1)) / rate_change)}\n",
            string=osu_file_content,
            count=1,
        )

    # update beatmap id
    osu_file_content = re.sub(
        pattern=r"\nBeatmapID:\d+\n",
        repl=rf"\nBeatmapID:{new_beatmap_id}\n",
        string=osu_file_content,
        count=1,
    )

    # update version
    osu_file_content = re.sub(
        pattern=rf"\nVersion:{re.escape(original_version)}\n",
        repl=f"\nVersion:{new_version}\n",
        string=osu_file_content,
        count=1,
    )

    # append 'osutrainer' tag
    # TODO: could use a different 'bancho.py' tag?
    osu_file_content = re.sub(
        # TODO: am i adding an extra space?
        pattern=r"\nTags:( *(?:.+))?\n",
        repl=r"\nTags:\1 osutrainer\n",
        string=osu_file_content,
        count=1,
    )

    return osu_file_content
