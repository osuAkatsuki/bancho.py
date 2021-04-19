# -*- coding: utf-8 -*-
import re
from cmyui.discord import Webhook
from cmyui.discord import Embed

from objects import glob
from objects.score import Score
from objects.player import Player
from objects.beatmap import Beatmap

WEBHOOK = glob.config.webhooks['chat-bridge']

GRADE_THUMBNAILS = {
  "XH": "https://cdn.discordapp.com/emojis/833673474836660265.png?v=1",
  "SH": "https://cdn.discordapp.com/emojis/833673474277900318.png?v=1",
  "X":  "https://cdn.discordapp.com/emojis/833673474270167060.png?v=1",
  "S":  "https://cdn.discordapp.com/emojis/833673474022572032.png?v=1",
  "A":  "https://cdn.discordapp.com/emojis/833673433941934091.png?v=1",
  "B":  "https://cdn.discordapp.com/emojis/833673434122289172.png?v=1",
  "C":  "https://cdn.discordapp.com/emojis/833673433656721418.png?v=1",
  "D":  "https://cdn.discordapp.com/emojis/833673433408733194.png?v=1",
  "F":  "",
  "N":  ""
}

GRADE_COLORS = {
  "XH": 0xE0F7FA, #Silver SS
  "SH": 0xE0F7FA, #Silver S
  "X":  0xFFEB3B, #SS
  "S":  0xFFEB3B, #S
  "A":  0x8BC34A,
  "B":  0x2196F3,
  "C":  0x9C27B0,
  "D":  0xF44336,
  "F":  0x212121,
  "N":  0x212121
}

MOD_EMOTES = {
  'NF': "NF",
  'EZ': "EZ",
  'TD': "TD",
  'HD': "HD",
  'HR': "HR",
  'SD': "SD",
  'DT': "DT",
  'RX': "RX",
  'HT': "HT",
  'NC': "NC",
  'FL': "FL",
  'AU': "AU",
  'SO': "SO",
  'AP': "AP",
  'PF': "PF",
  'FI': "FI",
  'RN': "RN",
  'CN': "CN",
  'TP': "TP",
  'V2': "V2",
  'MR': "MR",

  '1K': "1K",
  '2K': "2K",
  '3K': "3K",
  '4K': "4K",
  '5K': "5K",
  '6K': "6K",
  '7K': "7K",
  '8K': "8K",
  '9K': "9K",
  'CO': "CO",
}

async def sendNewScore(s: Score):
  wh = Webhook(url=WEBHOOK)

  diff=[f'{s.sr:.2f}★']
  if s.mods:
    diff.insert(1, f'({"".join(map(lambda mod: MOD_EMOTES[mod], re.findall("..",repr(s.mods).replace("DTNC","NC"))))})')

  e = Embed(title=s.bmap.full, url=f'https://osu.ppy.sh/b/{s.bmap.id}',color=GRADE_COLORS[s.grade])
  e.set_author(name=f'{s.player.name} achieved #{s.rank} on', url=f'https://osu.catgirl.moe/u/{s.player.id}', icon_url=f'https://a.osu.catgirl.moe/{s.player.id}')
  e.set_thumbnail(url=GRADE_THUMBNAILS[s.grade])
  e.add_field("Difficulty:", ' '.join(diff), True)
  e.add_field("Accuracy:", f'{s.acc:.2f}% ({s.pp:,.2f}pp)', True)
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