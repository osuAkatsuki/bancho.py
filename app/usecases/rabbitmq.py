import orjson
import aio_pika

import app.settings
import app.state.services
from app.objects.score import Score
from typing import Optional

def score_to_json(score: Score) -> Optional[str]:
    """Converts the specified score into a JSON object."""
    
    # TODO: refactor this way of creating the score json
    obj = {
        "id": score.id,
        "bmap": {
            "md5": score.bmap.md5,
            "id": score.bmap.id,
            "set_id": score.bmap.set_id,
            
            "artist": score.bmap.artist,
            "title": score.bmap.title,
            "version": score.bmap.version,
            "creator": score.bmap.creator,
            
            "last_update": score.bmap.last_update,
            "total_length": score.bmap.total_length,
            "max_combo": score.bmap.max_combo,
            
            "status": score.bmap.status,
            "frozen": score.bmap.frozen,
            
            "plays": score.bmap.plays,
            "passes": score.bmap.passes,
            "mode": score.bmap.mode,
            "bpm": score.bmap.bpm,
            
            "cs": score.bmap.cs,
            "od": score.bmap.od,
            "ar": score.bmap.ar,
            "hp": score.bmap.hp,
            
            "diff": score.bmap.diff,
            
            "filename": score.bmap.filename
        },
        "player": {
            "id": score.player.id,
            "name": score.player.name,
            "safe_name": score.player.safe_name,
            
            "priv": score.player.priv,
            
            "stats": {
                # Added manually later
            }            
        },
        
        "mode": score.mode,
        "mods": score.mods,
        
        "pp": score.pp,
        "sr": score.sr,
        "score": score.score,
        "max_combo": score.max_combo,
        "acc": score.acc,
        
        "n300": score.n300,
        "n100": score.n100,
        "n50": score.n50,
        "nmiss": score.nmiss,
        "ngeki": score.ngeki,
        "nkatu": score.nkatu,
        
        "grade": score.grade,
        
        "passed": score.passed,
        "perfect": score.perfect,
        "status": score.status,
        
        "client_time": score.client_time,
        "time_elapsed": score.time_elapsed,
        
        "rank": score.rank
    }
    
    #for mode, data in score.player.stats.items():
    #    obj["player"]["stats"][mode]["tscore"] = data.tscore
    #    obj["player"]["stats"][mode]["rscore"] = data.rscore
    #    obj["player"]["stats"][mode]["pp"] = data.pphe
    #    obj["player"]["stats"][mode]["acc"] = data.acc
    #    obj["player"]["stats"][mode]["plays"] = data.plays
    #    obj["player"]["stats"][mode]["playtime"] = data.playtime
    #    obj["player"]["stats"][mode]["max_combo"] = data.max_combo
    #    obj["player"]["stats"][mode]["total_hits"] = data.total_hits
    #    obj["player"]["stats"][mode]["rank"] = data.rank
    
    return orjson.dumps(obj)

async def enqueue_submitted_score(score: Score) -> None:
    """Enqueues the score from the score submission in the rabbitmq queue."""
    
    if not app.settings.RABBITMQ_ENABLED:
        return
    
    await app.state.services.amqp_channel.default_exchange.publish(
        aio_pika.Message(body=score_to_json(score)),
        routing_key="bpy.score_submission_queue"
    )