from __future__ import annotations
import math
from typing import Dict, Any
import app.state.services

async def update_player_pp_aggregates(player_id: int) -> None:
    # Fetch all stats for listed modes
    stats_rows = await app.state.services.database.fetch_all(
        "SELECT mode, pp FROM stats WHERE id = :player_id AND mode IN (0,1,2,3,4,5,6,8)",
        {"player_id": player_id}
    )

    if not stats_rows:
        return

    # Group pp by needed categories
    mode_pp: Dict[int, float] = {}
    for row in stats_rows:
        mode_pp[row["mode"]] = row["pp"]

    # Helper: totals for aggregates
    def calculate_stats(pp_values):
        if not pp_values:
            return (0, 0)
        total = sum(pp_values)
        mean = total / len(pp_values)
        variance = sum((x - mean) ** 2 for x in pp_values) / max(len(pp_values)-1, 1)
        stddev = 0 if len(pp_values) <= 1 else total - 2 * math.sqrt(variance)
        return (round(total), round(stddev))
    
    # Individual mode values (with defaults)
    pp_std = mode_pp.get(0, 0)
    pp_std_rx = mode_pp.get(4, 0)
    pp_std_ap = mode_pp.get(8, 0)
    pp_taiko = mode_pp.get(1, 0)
    pp_taiko_rx = mode_pp.get(5, 0)
    pp_catch = mode_pp.get(2, 0)
    pp_catch_rx = mode_pp.get(6, 0)
    pp_mania = mode_pp.get(3, 0)

    # Groupings for aggregates
    all_modes = [mode_pp.get(i, 0) for i in [0,1,2,3,4,5,6,8]]
    classic = [mode_pp.get(i, 0) for i in [0,1,2,3]]
    relax = [mode_pp.get(i, 0) for i in [4,5,6]]
    
    std_group = [mode_pp.get(i, 0) for i in [0,4,8]]      # osu, osu relax, osu autopilot
    taiko_group = [mode_pp.get(i, 0) for i in [1,5]]      # taiko, taiko relax
    catch_group = [mode_pp.get(i, 0) for i in [2,6]]      # catch, catch relax

    # Compute all totals/stddevs
    all_total, all_stddev = calculate_stats([v for v in all_modes if v])
    classic_total, classic_stddev = calculate_stats([v for v in classic if v])
    relax_total, relax_stddev = calculate_stats([v for v in relax if v])
    std_total, std_stddev = calculate_stats([v for v in std_group if v])
    taiko_total, taiko_stddev = calculate_stats([v for v in taiko_group if v])
    catch_total, catch_stddev = calculate_stats([v for v in catch_group if v])

    # UPSERT new record with all fields
    await app.state.services.database.execute(
        """
        REPLACE INTO player_pp_aggregates (
            player_id,
            pp_std, pp_std_rx, pp_std_ap,
            pp_taiko, pp_taiko_rx,
            pp_catch, pp_catch_rx,
            pp_mania,
            pp_total_all_modes, pp_stddev_all_modes,
            pp_total_classic, pp_stddev_classic,
            pp_total_relax, pp_stddev_relax,
            pp_total_std, pp_total_taiko, pp_total_catch,
            pp_stddev_std, pp_stddev_taiko, pp_stddev_catch
        ) VALUES (
            :player_id,
            :pp_std, :pp_std_rx, :pp_std_ap,
            :pp_taiko, :pp_taiko_rx,
            :pp_catch, :pp_catch_rx,
            :pp_mania,
            :pp_total_all_modes, :pp_stddev_all_modes,
            :pp_total_classic, :pp_stddev_classic,
            :pp_total_relax, :pp_stddev_relax,
            :pp_total_std, :pp_total_taiko, :pp_total_catch,
            :pp_stddev_std, :pp_stddev_taiko, :pp_stddev_catch
        )
        """,
        {
            "player_id": player_id,
            "pp_std": pp_std, "pp_std_rx": pp_std_rx, "pp_std_ap": pp_std_ap,
            "pp_taiko": pp_taiko, "pp_taiko_rx": pp_taiko_rx,
            "pp_catch": pp_catch, "pp_catch_rx": pp_catch_rx,
            "pp_mania": pp_mania,
            "pp_total_all_modes": all_total, "pp_stddev_all_modes": all_stddev,
            "pp_total_classic": classic_total, "pp_stddev_classic": classic_stddev,
            "pp_total_relax": relax_total, "pp_stddev_relax": relax_stddev,
            "pp_total_std": std_total, "pp_total_taiko": taiko_total, "pp_total_catch": catch_total,
            "pp_stddev_std": std_stddev, "pp_stddev_taiko": taiko_stddev, "pp_stddev_catch": catch_stddev
        }
    )
