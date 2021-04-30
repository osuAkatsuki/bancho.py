# This file contains any sql updates, along with the
# version they are required from. Touching this without
# at least reading utils/updater.py is certainly a bad idea :)

# v3.0.6
alter table users change name_safe safe_name varchar(32) not null;
alter table users drop key users_name_safe_uindex;
alter table users add constraint users_safe_name_uindex unique (safe_name);
alter table users change pw_hash pw_bcrypt char(60) not null;
insert into channels (name, topic, read_priv, write_priv, auto_join) values
  ('#supporter', 'General discussion for p2w gamers.', 48, 48, false),
  ('#staff', 'General discussion for the cool kids.', 28672, 28672, true),
  ('#admin', 'General discussion for the cool.', 24576, 24576, true),
  ('#dev',   'General discussion for the.', 16384, 16384, true);

# v3.0.8
alter table users modify safe_name varchar(32) charset utf8 not null;
alter table users modify name varchar(32) charset utf8 not null;
alter table mail modify msg varchar(2048) charset utf8 not null;
alter table logs modify msg varchar(2048) charset utf8 not null;
drop table if exists comments;
create table comments
(
	id int auto_increment
		primary key,
	target_id int not null comment 'replay, map, or set id',
	target_type enum('replay', 'map', 'song') not null,
	userid int not null,
	time int not null,
	comment varchar(80) charset utf8 not null,
	colour char(6) null comment 'rgb hex string'
);

# v3.0.9
alter table stats modify tscore_vn_std int(11) unsigned default 0 not null;
alter table stats modify tscore_vn_taiko int(11) unsigned default 0 not null;
alter table stats modify tscore_vn_catch int(11) unsigned default 0 not null;
alter table stats modify tscore_vn_mania int(11) unsigned default 0 not null;
alter table stats modify tscore_rx_std int(11) unsigned default 0 not null;
alter table stats modify tscore_rx_taiko int(11) unsigned default 0 not null;
alter table stats modify tscore_rx_catch int(11) unsigned default 0 not null;
alter table stats modify tscore_ap_std int(11) unsigned default 0 not null;
alter table stats modify rscore_vn_std int(11) unsigned default 0 not null;
alter table stats modify rscore_vn_taiko int(11) unsigned default 0 not null;
alter table stats modify rscore_vn_catch int(11) unsigned default 0 not null;
alter table stats modify rscore_vn_mania int(11) unsigned default 0 not null;
alter table stats modify rscore_rx_std int(11) unsigned default 0 not null;
alter table stats modify rscore_rx_taiko int(11) unsigned default 0 not null;
alter table stats modify rscore_rx_catch int(11) unsigned default 0 not null;
alter table stats modify rscore_ap_std int(11) unsigned default 0 not null;
alter table stats modify pp_vn_std smallint(6) unsigned default 0 not null;
alter table stats modify pp_vn_taiko smallint(6) unsigned default 0 not null;
alter table stats modify pp_vn_catch smallint(6) unsigned default 0 not null;
alter table stats modify pp_vn_mania smallint(6) unsigned default 0 not null;
alter table stats modify pp_rx_std smallint(6) unsigned default 0 not null;
alter table stats modify pp_rx_taiko smallint(6) unsigned default 0 not null;
alter table stats modify pp_rx_catch smallint(6) unsigned default 0 not null;
alter table stats modify pp_ap_std smallint(6) unsigned default 0 not null;
alter table stats modify plays_vn_std int(11) unsigned default 0 not null;
alter table stats modify plays_vn_taiko int(11) unsigned default 0 not null;
alter table stats modify plays_vn_catch int(11) unsigned default 0 not null;
alter table stats modify plays_vn_mania int(11) unsigned default 0 not null;
alter table stats modify plays_rx_std int(11) unsigned default 0 not null;
alter table stats modify plays_rx_taiko int(11) unsigned default 0 not null;
alter table stats modify plays_rx_catch int(11) unsigned default 0 not null;
alter table stats modify plays_ap_std int(11) unsigned default 0 not null;
alter table stats modify playtime_vn_std int(11) unsigned default 0 not null;
alter table stats modify playtime_vn_taiko int(11) unsigned default 0 not null;
alter table stats modify playtime_vn_catch int(11) unsigned default 0 not null;
alter table stats modify playtime_vn_mania int(11) unsigned default 0 not null;
alter table stats modify playtime_rx_std int(11) unsigned default 0 not null;
alter table stats modify playtime_rx_taiko int(11) unsigned default 0 not null;
alter table stats modify playtime_rx_catch int(11) unsigned default 0 not null;
alter table stats modify playtime_ap_std int(11) unsigned default 0 not null;
alter table stats modify maxcombo_vn_std int(11) unsigned default 0 not null;
alter table stats modify maxcombo_vn_taiko int(11) unsigned default 0 not null;
alter table stats modify maxcombo_vn_catch int(11) unsigned default 0 not null;
alter table stats modify maxcombo_vn_mania int(11) unsigned default 0 not null;
alter table stats modify maxcombo_rx_std int(11) unsigned default 0 not null;
alter table stats modify maxcombo_rx_taiko int(11) unsigned default 0 not null;
alter table stats modify maxcombo_rx_catch int(11) unsigned default 0 not null;
alter table stats modify maxcombo_ap_std int(11) unsigned default 0 not null;

# v3.0.10
update channels set write_priv = 24576 where name = '#announce';

# v3.1.0
alter table maps modify bpm float(12,2) default 0.00 not null;
alter table stats modify tscore_vn_std bigint(21) unsigned default 0 not null;
alter table stats modify tscore_vn_taiko bigint(21) unsigned default 0 not null;
alter table stats modify tscore_vn_catch bigint(21) unsigned default 0 not null;
alter table stats modify tscore_vn_mania bigint(21) unsigned default 0 not null;
alter table stats modify tscore_rx_std bigint(21) unsigned default 0 not null;
alter table stats modify tscore_rx_taiko bigint(21) unsigned default 0 not null;
alter table stats modify tscore_rx_catch bigint(21) unsigned default 0 not null;
alter table stats modify tscore_ap_std bigint(21) unsigned default 0 not null;
alter table stats modify rscore_vn_std bigint(21) unsigned default 0 not null;
alter table stats modify rscore_vn_taiko bigint(21) unsigned default 0 not null;
alter table stats modify rscore_vn_catch bigint(21) unsigned default 0 not null;
alter table stats modify rscore_vn_mania bigint(21) unsigned default 0 not null;
alter table stats modify rscore_rx_std bigint(21) unsigned default 0 not null;
alter table stats modify rscore_rx_taiko bigint(21) unsigned default 0 not null;
alter table stats modify rscore_rx_catch bigint(21) unsigned default 0 not null;
alter table stats modify rscore_ap_std bigint(21) unsigned default 0 not null;
alter table stats modify pp_vn_std int(11) unsigned default 0 not null;
alter table stats modify pp_vn_taiko int(11) unsigned default 0 not null;
alter table stats modify pp_vn_catch int(11) unsigned default 0 not null;
alter table stats modify pp_vn_mania int(11) unsigned default 0 not null;
alter table stats modify pp_rx_std int(11) unsigned default 0 not null;
alter table stats modify pp_rx_taiko int(11) unsigned default 0 not null;
alter table stats modify pp_rx_catch int(11) unsigned default 0 not null;
alter table stats modify pp_ap_std int(11) unsigned default 0 not null;

# v3.1.2
create table clans
(
	id int auto_increment
		primary key,
	name varchar(16) not null,
	tag varchar(6) not null,
	owner int not null,
	created_at datetime not null,
	constraint clans_name_uindex
		unique (name),
	constraint clans_owner_uindex
		unique (owner),
	constraint clans_tag_uindex
		unique (tag)
);
alter table users add clan_id int default 0 not null;
alter table users add clan_rank tinyint(1) default 0 not null;
create table achievements
(
	id int auto_increment
		primary key,
	file varchar(128) not null,
	name varchar(128) not null,
	`desc` varchar(256) not null,
	cond varchar(64) not null,
	mode tinyint(1) not null,
	constraint achievements_desc_uindex
		unique (`desc`),
	constraint achievements_file_uindex
		unique (file),
	constraint achievements_name_uindex
		unique (name)
);
create table user_achievements
(
	userid int not null,
	achid int not null,
	primary key (userid, achid)
);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (1, 'osu-skill-pass-1', 'Rising Star', 'Can''t go forward without the first steps.', '(score.mods & 259 == 0) and 2 >= score.sr > 1', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (2, 'osu-skill-pass-2', 'Constellation Prize', 'Definitely not a consolation prize. Now things start getting hard!', '(score.mods & 259 == 0) and 3 >= score.sr > 2', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (3, 'osu-skill-pass-3', 'Building Confidence', 'Oh, you''ve SO got this.', '(score.mods & 259 == 0) and 4 >= score.sr > 3', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (4, 'osu-skill-pass-4', 'Insanity Approaches', 'You''re not twitching, you''re just ready.', '(score.mods & 259 == 0) and 5 >= score.sr > 4', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (5, 'osu-skill-pass-5', 'These Clarion Skies', 'Everything seems so clear now.', '(score.mods & 259 == 0) and 6 >= score.sr > 5', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (6, 'osu-skill-pass-6', 'Above and Beyond', 'A cut above the rest.', '(score.mods & 259 == 0) and 7 >= score.sr > 6', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (7, 'osu-skill-pass-7', 'Supremacy', 'All marvel before your prowess.', '(score.mods & 259 == 0) and 8 >= score.sr > 7', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (8, 'osu-skill-pass-8', 'Absolution', 'My god, you''re full of stars!', '(score.mods & 259 == 0) and 9 >= score.sr > 8', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (9, 'osu-skill-pass-9', 'Event Horizon', 'No force dares to pull you under.', '(score.mods & 259 == 0) and 10 >= score.sr > 9', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (10, 'osu-skill-pass-10', 'Phantasm', 'Fevered is your passion, extraordinary is your skill.', '(score.mods & 259 == 0) and 11 >= score.sr > 10', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (11, 'osu-skill-fc-1', 'Totality', 'All the notes. Every single one.', 'score.perfect and 2 >= score.sr > 1', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (12, 'osu-skill-fc-2', 'Business As Usual', 'Two to go, please.', 'score.perfect and 3 >= score.sr > 2', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (13, 'osu-skill-fc-3', 'Building Steam', 'Hey, this isn''t so bad.', 'score.perfect and 4 >= score.sr > 3', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (14, 'osu-skill-fc-4', 'Moving Forward', 'Bet you feel good about that.', 'score.perfect and 5 >= score.sr > 4', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (15, 'osu-skill-fc-5', 'Paradigm Shift', 'Surprisingly difficult.', 'score.perfect and 6 >= score.sr > 5', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (16, 'osu-skill-fc-6', 'Anguish Quelled', 'Don''t choke.', 'score.perfect and 7 >= score.sr > 6', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (17, 'osu-skill-fc-7', 'Never Give Up', 'Excellence is its own reward.', 'score.perfect and 8 >= score.sr > 7', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (18, 'osu-skill-fc-8', 'Aberration', 'They said it couldn''t be done. They were wrong.', 'score.perfect and 9 >= score.sr > 8', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (19, 'osu-skill-fc-9', 'Chosen', 'Reign among the Prometheans, where you belong.', 'score.perfect and 10 >= score.sr > 9', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (20, 'osu-skill-fc-10', 'Unfathomable', 'You have no equal.', 'score.perfect and 11 >= score.sr > 10', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (21, 'osu-combo-500', '500 Combo', '500 big ones! You''re moving up in the world!', '750 >= score.max_combo > 500', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (22, 'osu-combo-750', '750 Combo', '750 notes back to back? Woah.', '1000 >= score.max_combo > 750', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (23, 'osu-combo-1000', '1000 Combo', 'A thousand reasons why you rock at this game.', '2000 >= score.max_combo > 1000', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (24, 'osu-combo-2000', '2000 Combo', 'Nothing can stop you now.', 'score.max_combo >= 2000', 0);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (25, 'taiko-skill-pass-1', 'My First Don', 'Marching to the beat of your own drum. Literally.', '(score.mods & 259 == 0) and 2 >= score.sr > 1', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (26, 'taiko-skill-pass-2', 'Katsu Katsu Katsu', 'Hora! Izuko!', '(score.mods & 259 == 0) and 3 >= score.sr > 2', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (27, 'taiko-skill-pass-3', 'Not Even Trying', 'Muzukashii? Not even.', '(score.mods & 259 == 0) and 4 >= score.sr > 3', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (28, 'taiko-skill-pass-4', 'Face Your Demons', 'The first trials are now behind you, but are you a match for the Oni?', '(score.mods & 259 == 0) and 5 >= score.sr > 4', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (29, 'taiko-skill-pass-5', 'The Demon Within', 'No rest for the wicked.', '(score.mods & 259 == 0) and 6 >= score.sr > 5', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (30, 'taiko-skill-pass-6', 'Drumbreaker', 'Too strong.', '(score.mods & 259 == 0) and 7 >= score.sr > 6', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (31, 'taiko-skill-pass-7', 'The Godfather', 'You are the Don of Dons.', '(score.mods & 259 == 0) and 8 >= score.sr > 7', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (32, 'taiko-skill-pass-8', 'Rhythm Incarnate', 'Feel the beat. Become the beat.', '(score.mods & 259 == 0) and 9 >= score.sr > 8', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (33, 'taiko-skill-fc-1', 'Keeping Time', 'Don, then katsu. Don, then katsu..', 'score.perfect and 2 >= score.sr > 1', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (34, 'taiko-skill-fc-2', 'To Your Own Beat', 'Straight and steady.', 'score.perfect and 3 >= score.sr > 2', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (35, 'taiko-skill-fc-3', 'Big Drums', 'Bigger scores to match.', 'score.perfect and 4 >= score.sr > 3', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (36, 'taiko-skill-fc-4', 'Adversity Overcome', 'Difficult? Not for you.', 'score.perfect and 5 >= score.sr > 4', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (37, 'taiko-skill-fc-5', 'Demonslayer', 'An Oni felled forevermore.', 'score.perfect and 6 >= score.sr > 5', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (38, 'taiko-skill-fc-6', 'Rhythm''s Call', 'Heralding true skill.', 'score.perfect and 7 >= score.sr > 6', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (39, 'taiko-skill-fc-7', 'Time Everlasting', 'Not a single beat escapes you.', 'score.perfect and 8 >= score.sr > 7', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (40, 'taiko-skill-fc-8', 'The Drummer''s Throne', 'Percussive brilliance befitting royalty alone.', 'score.perfect and 9 >= score.sr > 8', 1);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (41, 'fruits-skill-pass-1', 'A Slice Of Life', 'Hey, this fruit catching business isn''t bad.', '(score.mods & 259 == 0) and 2 >= score.sr > 1', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (42, 'fruits-skill-pass-2', 'Dashing Ever Forward', 'Fast is how you do it.', '(score.mods & 259 == 0) and 3 >= score.sr > 2', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (43, 'fruits-skill-pass-3', 'Zesty Disposition', 'No scurvy for you, not with that much fruit.', '(score.mods & 259 == 0) and 4 >= score.sr > 3', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (44, 'fruits-skill-pass-4', 'Hyperdash ON!', 'Time and distance is no obstacle to you.', '(score.mods & 259 == 0) and 5 >= score.sr > 4', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (45, 'fruits-skill-pass-5', 'It''s Raining Fruit', 'And you can catch them all.', '(score.mods & 259 == 0) and 6 >= score.sr > 5', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (46, 'fruits-skill-pass-6', 'Fruit Ninja', 'Legendary techniques.', '(score.mods & 259 == 0) and 7 >= score.sr > 6', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (47, 'fruits-skill-pass-7', 'Dreamcatcher', 'No fruit, only dreams now.', '(score.mods & 259 == 0) and 8 >= score.sr > 7', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (48, 'fruits-skill-pass-8', 'Lord of the Catch', 'Your kingdom kneels before you.', '(score.mods & 259 == 0) and 9 >= score.sr > 8', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (49, 'fruits-skill-fc-1', 'Sweet And Sour', 'Apples and oranges, literally.', 'score.perfect and 2 >= score.sr > 1', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (50, 'fruits-skill-fc-2', 'Reaching The Core', 'The seeds of future success.', 'score.perfect and 3 >= score.sr > 2', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (51, 'fruits-skill-fc-3', 'Clean Platter', 'Clean only of failure. It is completely full, otherwise.', 'score.perfect and 4 >= score.sr > 3', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (52, 'fruits-skill-fc-4', 'Between The Rain', 'No umbrella needed.', 'score.perfect and 5 >= score.sr > 4', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (53, 'fruits-skill-fc-5', 'Addicted', 'That was an overdose?', 'score.perfect and 6 >= score.sr > 5', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (54, 'fruits-skill-fc-6', 'Quickening', 'A dash above normal limits.', 'score.perfect and 7 >= score.sr > 6', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (55, 'fruits-skill-fc-7', 'Supersonic', 'Faster than is reasonably necessary.', 'score.perfect and 8 >= score.sr > 7', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (56, 'fruits-skill-fc-8', 'Dashing Scarlet', 'Speed beyond mortal reckoning.', 'score.perfect and 9 >= score.sr > 8', 2);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (57, 'mania-skill-pass-1', 'First Steps', 'It isn''t 9-to-5, but 1-to-9. Keys, that is.', '(score.mods & 259 == 0) and 2 >= score.sr > 1', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (58, 'mania-skill-pass-2', 'No Normal Player', 'Not anymore, at least.', '(score.mods & 259 == 0) and 3 >= score.sr > 2', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (59, 'mania-skill-pass-3', 'Impulse Drive', 'Not quite hyperspeed, but getting close.', '(score.mods & 259 == 0) and 4 >= score.sr > 3', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (60, 'mania-skill-pass-4', 'Hyperspeed', 'Woah.', '(score.mods & 259 == 0) and 5 >= score.sr > 4', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (61, 'mania-skill-pass-5', 'Ever Onwards', 'Another challenge is just around the corner.', '(score.mods & 259 == 0) and 6 >= score.sr > 5', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (62, 'mania-skill-pass-6', 'Another Surpassed', 'Is there no limit to your skills?', '(score.mods & 259 == 0) and 7 >= score.sr > 6', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (63, 'mania-skill-pass-7', 'Extra Credit', 'See me after class.', '(score.mods & 259 == 0) and 8 >= score.sr > 7', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (64, 'mania-skill-pass-8', 'Maniac', 'There''s just no stopping you.', '(score.mods & 259 == 0) and 9 >= score.sr > 8', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (65, 'mania-skill-fc-1', 'Keystruck', 'The beginning of a new story', 'score.perfect and (score.mods & 259 == 0) and 2 >= score.sr > 1', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (66, 'mania-skill-fc-2', 'Keying In', 'Finding your groove.', 'score.perfect and 3 >= score.sr > 2', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (67, 'mania-skill-fc-3', 'Hyperflow', 'You can *feel* the rhythm.', 'score.perfect and 4 >= score.sr > 3', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (68, 'mania-skill-fc-4', 'Breakthrough', 'Many skills mastered, rolled into one.', 'score.perfect and 5 >= score.sr > 4', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (69, 'mania-skill-fc-5', 'Everything Extra', 'Giving your all is giving everything you have.', 'score.perfect and 6 >= score.sr > 5', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (70, 'mania-skill-fc-6', 'Level Breaker', 'Finesse beyond reason', 'score.perfect and 7 >= score.sr > 6', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (71, 'mania-skill-fc-7', 'Step Up', 'A precipice rarely seen.', 'score.perfect and 8 >= score.sr > 7', 3);
insert into achievements (`id`, `file`, `name`, `desc`, `cond`, `mode`) values (72, 'mania-skill-fc-8', 'Behind The Veil', 'Supernatural!', 'score.perfect and 9 >= score.sr > 8', 3);

# v3.1.3
alter table clans modify name varchar(16) charset utf8 not null;
alter table clans modify tag varchar(6) charset utf8 not null;
alter table achievements modify name varchar(128) charset utf8 not null;
alter table achievements modify `desc` varchar(256) charset utf8 not null;
alter table maps modify artist varchar(128) charset utf8 not null;
alter table maps modify title varchar(128) charset utf8 not null;
alter table maps modify version varchar(128) charset utf8 not null;
alter table maps modify creator varchar(19) charset utf8 not null comment 'not 100%% certain on len';
alter table tourney_pools drop foreign key tourney_pools_users_id_fk;
alter table tourney_pool_maps drop foreign key tourney_pool_maps_tourney_pools_id_fk;
alter table stats drop foreign key stats_users_id_fk;
alter table ratings drop foreign key ratings_maps_md5_fk;
alter table ratings drop foreign key ratings_users_id_fk;
alter table logs modify `from` int not null comment 'both from and to are playerids';

# v3.1.9
alter table scores_rx modify id bigint(20) unsigned auto_increment;
update scores_rx set id = id + (6148914691236517205 - 1);
select @max_rx := MAX(id) + 1 from scores_rx;
set @s = CONCAT('alter table scores_rx auto_increment = ', @max_rx);
prepare stmt from @s;
execute stmt;
deallocate PREPARE stmt;
alter table scores_ap modify id bigint(20) unsigned auto_increment;
update scores_ap set id = id + (12297829382473034410 - 1);
select @max_ap := MAX(id) + 1 from scores_ap;
set @s = CONCAT('alter table scores_ap auto_increment = ', @max_ap);
prepare stmt from @s;
execute stmt;
deallocate PREPARE stmt;
alter table performance_reports modify scoreid bigint(20) unsigned auto_increment;

# v3.2.0
create table map_requests
(
	id int auto_increment
		primary key,
	map_id int not null,
	player_id int not null,
	datetime datetime not null,
	active tinyint(1) not null
);

# v3.2.1
update scores_rx set id = id - 3074457345618258603;
update scores_ap set id = id - 6148914691236517206;

# v3.2.2
alter table maps add max_combo int not null after total_length;
alter table users change clan_rank clan_priv tinyint(1) default 0 not null;

# v3.2.3
alter table users add api_key char(36) default NULL null;
create unique index users_api_key_uindex on users (api_key);

# v3.2.4
update achievements set file = replace(file, 'ctb', 'fruits') where mode = 2;

# v3.2.5
update achievements set cond = '(score.mods & 1 == 0) and 1 <= score.sr < 2' where file in ('osu-skill-pass-1', 'taiko-skill-pass-1', 'fruits-skill-pass-1', 'mania-skill-pass-1');
update achievements set cond = '(score.mods & 1 == 0) and 2 <= score.sr < 3' where file in ('osu-skill-pass-2', 'taiko-skill-pass-2', 'fruits-skill-pass-2', 'mania-skill-pass-2');
update achievements set cond = '(score.mods & 1 == 0) and 3 <= score.sr < 4' where file in ('osu-skill-pass-3', 'taiko-skill-pass-3', 'fruits-skill-pass-3', 'mania-skill-pass-3');
update achievements set cond = '(score.mods & 1 == 0) and 4 <= score.sr < 5' where file in ('osu-skill-pass-4', 'taiko-skill-pass-4', 'fruits-skill-pass-4', 'mania-skill-pass-4');
update achievements set cond = '(score.mods & 1 == 0) and 5 <= score.sr < 6' where file in ('osu-skill-pass-5', 'taiko-skill-pass-5', 'fruits-skill-pass-5', 'mania-skill-pass-5');
update achievements set cond = '(score.mods & 1 == 0) and 6 <= score.sr < 7' where file in ('osu-skill-pass-6', 'taiko-skill-pass-6', 'fruits-skill-pass-6', 'mania-skill-pass-6');
update achievements set cond = '(score.mods & 1 == 0) and 7 <= score.sr < 8' where file in ('osu-skill-pass-7', 'taiko-skill-pass-7', 'fruits-skill-pass-7', 'mania-skill-pass-7');
update achievements set cond = '(score.mods & 1 == 0) and 8 <= score.sr < 9' where file in ('osu-skill-pass-8', 'taiko-skill-pass-8', 'fruits-skill-pass-8', 'mania-skill-pass-8');
update achievements set cond = '(score.mods & 1 == 0) and 9 <= score.sr < 10' where file = 'osu-skill-pass-9';
update achievements set cond = '(score.mods & 1 == 0) and 10 <= score.sr < 11' where file = 'osu-skill-pass-10';

update achievements set cond = 'score.perfect and 1 <= score.sr < 2' where file in ('osu-skill-fc-1', 'taiko-skill-fc-1', 'fruits-skill-fc-1', 'mania-skill-fc-1');
update achievements set cond = 'score.perfect and 2 <= score.sr < 3' where file in ('osu-skill-fc-2', 'taiko-skill-fc-2', 'fruits-skill-fc-2', 'mania-skill-fc-2');
update achievements set cond = 'score.perfect and 3 <= score.sr < 4' where file in ('osu-skill-fc-3', 'taiko-skill-fc-3', 'fruits-skill-fc-3', 'mania-skill-fc-3');
update achievements set cond = 'score.perfect and 4 <= score.sr < 5' where file in ('osu-skill-fc-4', 'taiko-skill-fc-4', 'fruits-skill-fc-4', 'mania-skill-fc-4');
update achievements set cond = 'score.perfect and 5 <= score.sr < 6' where file in ('osu-skill-fc-5', 'taiko-skill-fc-5', 'fruits-skill-fc-5', 'mania-skill-fc-5');
update achievements set cond = 'score.perfect and 6 <= score.sr < 7' where file in ('osu-skill-fc-6', 'taiko-skill-fc-6', 'fruits-skill-fc-6', 'mania-skill-fc-6');
update achievements set cond = 'score.perfect and 7 <= score.sr < 8' where file in ('osu-skill-fc-7', 'taiko-skill-fc-7', 'fruits-skill-fc-7', 'mania-skill-fc-7');
update achievements set cond = 'score.perfect and 8 <= score.sr < 9' where file in ('osu-skill-fc-8', 'taiko-skill-fc-8', 'fruits-skill-fc-8', 'mania-skill-fc-8');
update achievements set cond = 'score.perfect and 9 <= score.sr < 10' where file = 'osu-skill-fc-9';
update achievements set cond = 'score.perfect and 10 <= score.sr < 11' where file = 'osu-skill-fc-10';

update achievements set cond = '500 <= score.max_combo < 750' where file = 'osu-combo-500';
update achievements set cond = '750 <= score.max_combo < 1000' where file = 'osu-combo-750';
update achievements set cond = '1000 <= score.max_combo < 2000' where file = 'osu-combo-1000';
update achievements set cond = '2000 <= score.max_combo' where file = 'osu-combo-2000';

# v3.2.6
alter table stats change maxcombo_vn_std max_combo_vn_std int(11) unsigned default 0 not null;
alter table stats change maxcombo_vn_taiko max_combo_vn_taiko int(11) unsigned default 0 not null;
alter table stats change maxcombo_vn_catch max_combo_vn_catch int(11) unsigned default 0 not null;
alter table stats change maxcombo_vn_mania max_combo_vn_mania int(11) unsigned default 0 not null;
alter table stats change maxcombo_rx_std max_combo_rx_std int(11) unsigned default 0 not null;
alter table stats change maxcombo_rx_taiko max_combo_rx_taiko int(11) unsigned default 0 not null;
alter table stats change maxcombo_rx_catch max_combo_rx_catch int(11) unsigned default 0 not null;
alter table stats change maxcombo_ap_std max_combo_ap_std int(11) unsigned default 0 not null;

# v3.2.7
drop table if exists user_hashes;

# v3.3.0
rename table friendships to relationships;
alter table relationships add type enum('friend', 'block') not null;

# v3.3.1
create table ingame_logins
(
	id int auto_increment
		primary key,
	userid int not null,
	ip varchar(45) not null comment 'maxlen for ipv6',
	osu_ver date not null,
	osu_stream varchar(11) not null,
	datetime datetime not null
);
