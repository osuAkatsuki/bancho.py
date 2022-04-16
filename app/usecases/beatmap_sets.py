from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Sequence

import app.repositories.beatmap_sets
import app.repositories.osuapi_v1
import app.settings
import app.state.services
from app.objects.beatmap import Beatmap
from app.objects.beatmap import BeatmapSet
from app.objects.beatmap import RankedStatus


def all_officially_ranked_or_approved(beatmaps: Sequence[Beatmap]) -> bool:
    """Whether all of the maps in the set are
    ranked or approved on official servers."""
    for beatmap in beatmaps:
        if (
            beatmap.status not in (RankedStatus.Ranked, RankedStatus.Approved)
            or beatmap.frozen  # ranked/approved, but only on bancho.py
        ):
            return False
    return True


def all_officially_loved(beatmaps: Sequence[Beatmap]) -> bool:
    """Whether all of the maps in the set are
    loved on official servers."""
    for beatmap in beatmaps:
        if (
            beatmap.status != RankedStatus.Loved
            or beatmap.frozen  # loved, but only on bancho.py
        ):
            return False
    return True


def has_expired_cache(beatmap_set: BeatmapSet) -> bool:
    """Whether the cached version of the set is
    expired and needs an update from the osu!api."""
    # ranked & approved maps are update-locked.
    if all_officially_ranked_or_approved(beatmap_set.maps):
        return False

    current_datetime = datetime.now()

    # the delta between cache invalidations will increase depending
    # on how long it's been since the map was last updated on osu!
    last_map_update = max(bmap.last_update for bmap in beatmap_set.maps)
    update_delta = current_datetime - last_map_update

    # with a minimum of 2 hours, add 5 hours per year since it's update.
    # the formula for this is subject to adjustment in the future.
    check_delta = timedelta(hours=2 + ((5 / 365) * update_delta.days))

    # we'll consider it much less likely for a loved map to be updated;
    # it's possible but the mapper will remove their leaderboard doing so.
    if all_officially_loved(beatmap_set.maps):
        # TODO: it's still possible for this to happen and the delta can span
        # over multiple days quite easily here, there should be a command to
        # force a cache invalidation on the set. (normal privs if spam protected)
        check_delta *= 4

    return current_datetime > (beatmap_set.last_osuapi_check + check_delta)


async def _update_if_available(beatmap_set: BeatmapSet) -> None:
    """Fetch newest data from the osu!api, check for differences
    and propogate any update into our cache & database."""
    if not app.settings.OSU_API_KEY:
        return

    if api_data := await app.repositories.osuapi_v1.get_beatmaps(s=beatmap_set.id):
        old_maps = {bmap.id: bmap for bmap in beatmap_set.maps}
        new_maps = {int(api_map["beatmap_id"]): api_map for api_map in api_data}

        beatmap_set.last_osuapi_check = datetime.now()

        # delete maps from old_maps where old.id not in new_maps
        # update maps from old_maps where old.md5 != new.md5
        # add maps to old_maps where new.id not in old_maps

        updated_maps: list[Beatmap] = []  # TODO: optimize
        map_md5s_to_delete: set[str] = set()

        # find maps in our current state that've been deleted, or need updates
        for old_id, old_map in old_maps.items():
            if old_id not in new_maps:
                # delete map from old_maps
                map_md5s_to_delete.add(old_map.md5)
            else:
                new_map = new_maps[old_id]
                if old_map.md5 != new_map["file_md5"]:
                    # update map from old_maps
                    beatmap = Beatmap.from_osuapi_response(new_map)

                    if old_map.frozen:
                        # maintain freeze & ranked status
                        beatmap.frozen = True
                        beatmap.status = old_map.status

                    updated_maps.append(beatmap)
                else:
                    # map is the same, make no changes
                    updated_maps.append(old_map)  # TODO: is this needed?

        # find maps that aren't in our current state, and add them
        for new_id, new_map in new_maps.items():
            if new_id not in old_maps:
                # new map we don't have locally, add it
                beatmap = Beatmap.from_osuapi_response(new_map)
                updated_maps.append(beatmap)

        # save changes to cache
        beatmap_set.maps = updated_maps

        # save changes to sql

        if map_md5s_to_delete:
            # delete maps
            await app.state.services.database.execute(
                "DELETE FROM maps WHERE md5 IN :map_md5s",
                {"map_md5s": map_md5s_to_delete},
            )

            # delete scores on the maps
            # TODO: if we add FKs to db, won't need this?
            await app.state.services.database.execute(
                "DELETE FROM scores WHERE map_md5 IN :map_md5s",
                {"map_md5s": map_md5s_to_delete},
            )

        # update last_osuapi_check
        await app.state.services.database.execute(
            "REPLACE INTO mapsets "
            "(server, id, last_osuapi_check) "
            'VALUES ("osu!", :id, :last_osuapi_check)',
            {"id": beatmap_set.id, "last_osuapi_check": beatmap_set.last_osuapi_check},
        )

        # update maps in sql

        await app.repositories.beatmap_sets.save_to_sql(beatmap_set)
    else:
        # TODO: we have the map on disk but it's
        #       been removed from the osu!api.
        map_md5s_to_delete = {bmap.md5 for bmap in beatmap_set.maps}

        # delete maps
        await app.state.services.database.execute(
            "DELETE FROM maps WHERE md5 IN :map_md5s",
            {"map_md5s": map_md5s_to_delete},
        )

        # delete scores on the maps
        # TODO: if we add FKs to db, won't need this?
        await app.state.services.database.execute(
            "DELETE FROM scores WHERE map_md5 IN :map_md5s",
            {"map_md5s": map_md5s_to_delete},
        )

        # delete set
        await app.state.services.database.execute(
            "DELETE FROM mapsets WHERE id = :set_id",
            {"set_id": beatmap_set.id},
        )
