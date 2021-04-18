# -*- coding: utf-8 -*-

from cmyui.discord import Webhook
from cmyui.discord import Embed

from objects import glob
from objects.score import Score
from objects.player import Player
from objects.beatmap import Beatmap

WEBHOOK = glob.config.webhooks['chat-bridge']

RANK_EMOTES = {
  "XH": "<:rank_ssh:764911895803068426>",
  "SH": "<:rank_sh:764911895772921876>",
  "X":  "<:rank_ss:764911895882104842>",
  "S":  "<:rank_s:764911895773052928>",
  "A":  "<:rank_a:764911895446421516>",
  "B":  "<:rank_b:764911895727308800>",
  "C":  "<:rank_c:764911895827185696>",
  "D":  "<:rank_d:764911895819059260>",
  "F":  "<:rank_f:764911895429120021>",
  "N":  ""
}

async def sendNewScore(s: Score):
  wh = Webhook(url=WEBHOOK)

  diff=[f'{s.sr:.2f}★']
  if s.mods:
    diff.insert(1, f'({s.mods!r})')

  e = Embed(title=s.bmap.full, url=f'https://osu.ppy.sh/b/{s.bmap.id}',color=0xE91E63)
  e.set_author(name=f'{s.player.name} achieved #{s.rank} on', url=f'https://osu.catgirl.moe/u/{s.player.id}', icon_url=f'https://a.osu.catgirl.moe/{s.player.id}')
  e.add_field("Difficulty:", ' '.join(diff), True)
  e.add_field("Accuracy:", f'{s.acc:.2f}% {RANK_EMOTES[s.grade]} ({s.pp:,.2f}pp)', True)
  e.add_field("Score:", f'{s.score:,} ({s.max_combo:,}/{s.bmap.max_combo:,}x)', True)
  e.set_image(url=f'https://assets.ppy.sh/beatmaps/{s.bmap.set_id}/covers/cover.jpg')

  wh.add_embed(e)
  await wh.post(glob.http)

async def sendPlayerJoined(p: Player):
  wh = Webhook(url=WEBHOOK)

  s = p.stats[0]  

  e = Embed(color=0x8BC34A)
  e.set_author(name=f'{p.name} joined the server', url=f'https://osu.catgirl.moe/u/{p.id}', icon_url=f'https://a.osu.catgirl.moe/{p.id}')
  e.add_field("Rank:", f'#{s.rank} ({s.pp:,.0f}pp)', True)
  e.add_field("Accuracy:", f'{s.acc:.2f}% ({s.max_combo:,}x)', True)
  e.add_field("Score:", f'{s.tscore:,} ({float(s.playtime)/3600:.2f}h)', True)
  
  wh.add_embed(e)
  await wh.post(glob.http)

async def sendPlayerLeft(p: Player):
  wh = Webhook(url=WEBHOOK)

  s = p.stats[0] 

  e = Embed(color=0xF44336)
  e.set_author(name=f'{p.name} left the server', url=f'https://osu.catgirl.moe/u/{p.id}', icon_url=f'https://a.osu.catgirl.moe/{p.id}')
  e.add_field("Rank:", f'#{s.rank} ({s.pp:,.0f}pp)', True)
  e.add_field("Accuracy:", f'{s.acc:.2f}% ({s.max_combo:,}x)', True)
  e.add_field("Score:", f'{s.tscore:,} ({float(s.playtime)/3600:.2f}h)', True)
  
  wh.add_embed(e)
  await wh.post(glob.http)

async def sendRankUpdate(p: Player, b: Beatmap, s: str):
  wh = Webhook(url=WEBHOOK)

  e = Embed(title=b.full, url=f'https://osu.ppy.sh/b/{b.id}', color=0xE91E63)
  e.set_author(name=f'{p.name} {s} a map', url=f'https://osu.catgirl.moe/u/{p.id}', icon_url=f'https://a.osu.catgirl.moe/{p.id}')
  e.set_image(url=f'https://assets.ppy.sh/beatmaps/{b.set_id}/covers/cover.jpg')
  
  wh.add_embed(e)
  await wh.post(glob.http)

async def sendMessage(p: Player, m: str):
  wh = Webhook(url=WEBHOOK, username=p.name, avatar_url=f'https://a.osu.catgirl.moe/{p.id}', content=m.replace("@", "[@]"))
  await wh.post(glob.http)