create schema cmyui collate latin1_swedish_ci;

create table achievements
(
	id int auto_increment
		primary key,
	file varchar(128) not null,
	name varchar(128) charset utf8 not null,
	`desc` varchar(256) charset utf8 not null,
	cond varchar(64) not null,
	mode tinyint(1) not null,
	constraint achievements_desc_uindex
		unique (`desc`),
	constraint achievements_file_uindex
		unique (file),
	constraint achievements_name_uindex
		unique (name)
);

create table channels
(
	id int auto_increment
		primary key,
	name varchar(32) not null,
	topic varchar(256) not null,
	read_priv int default 1 not null,
	write_priv int default 2 not null,
	auto_join tinyint(1) default 0 not null,
	constraint channels_name_uindex
		unique (name)
);

create table clans
(
	id int auto_increment
		primary key,
	name varchar(16) charset utf8 not null,
	tag varchar(6) charset utf8 not null,
	owner int not null,
	created_at datetime not null,
	constraint clans_name_uindex
		unique (name),
	constraint clans_owner_uindex
		unique (owner),
	constraint clans_tag_uindex
		unique (tag)
);

create table client_hashes
(
	userid int not null,
	osupath char(32) not null,
	adapters char(32) not null,
	uninstall_id char(32) not null,
	disk_serial char(32) not null,
	latest_time datetime not null,
	occurrences int default 0 not null,
	primary key (userid, osupath, adapters, uninstall_id, disk_serial)
);

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

create table favourites
(
	userid int not null,
	setid int not null,
	primary key (userid, setid)
);

create table friendships
(
	user1 int not null,
	user2 int not null,
	primary key (user1, user2)
);

create table logs
(
	id int auto_increment
		primary key,
	`from` int not null comment 'both from and to are playerids',
	`to` int not null,
	msg varchar(2048) charset utf8 not null,
	time datetime not null on update CURRENT_TIMESTAMP
);

create table mail
(
	id int auto_increment
		primary key,
	from_id int not null,
	to_id int not null,
	msg varchar(2048) charset utf8 not null,
	time int null,
	`read` tinyint(1) default 0 not null
);

create table maps
(
	server enum('osu!', 'gulag') default 'osu!' not null,
	id int not null,
	set_id int not null,
	status int not null,
	md5 char(32) not null,
	artist varchar(128) charset utf8 not null,
	title varchar(128) charset utf8 not null,
	version varchar(128) charset utf8 not null,
	creator varchar(19) charset utf8 not null comment 'not 100% certain on len',
	last_update datetime not null,
	total_length int not null,
	max_combo int not null,
	frozen tinyint(1) default 0 not null,
	plays int default 0 not null,
	passes int default 0 not null,
	mode tinyint(1) default 0 not null,
	bpm float(12,2) default 0.00 not null,
	cs float(4,2) default 0.00 not null,
	ar float(4,2) default 0.00 not null,
	od float(4,2) default 0.00 not null,
	hp float(4,2) default 0.00 not null,
	diff float(6,3) default 0.000 not null,
	primary key (server, id),
	constraint maps_id_uindex
		unique (id),
	constraint maps_md5_uindex
		unique (md5)
);

create table map_requests
(
	id int auto_increment
		primary key,
	map_id int not null,
	player_id int not null,
	datetime datetime not null,
	active tinyint(1) not null
);

create table performance_reports
(
	scoreid bigint(20) unsigned not null,
	mod_mode enum('vanilla', 'relax', 'autopilot') default 'vanilla' not null,
	os varchar(64) not null,
	fullscreen tinyint(1) not null,
	fps_cap varchar(16) not null,
	compatibility tinyint(1) not null,
	version varchar(16) not null,
	start_time int not null,
	end_time int not null,
	frame_count int not null,
	spike_frames int not null,
	aim_rate int not null,
	completion tinyint(1) not null,
	identifier varchar(128) null comment 'really don''t know much about this yet',
	average_frametime int not null,
	primary key (scoreid, mod_mode)
);

create table ratings
(
	userid int not null,
	map_md5 char(32) not null,
	rating tinyint(2) not null,
	primary key (userid, map_md5),
	constraint ratings_map_md5_uindex
		unique (map_md5),
	constraint ratings_userid_uindex
		unique (userid)
);

create table scores_ap
(
	id bigint(20) unsigned auto_increment
		primary key,
	map_md5 char(32) not null,
	score int not null,
	pp float(7,3) not null,
	acc float(6,3) not null,
	max_combo int not null,
	mods int not null,
	n300 int not null,
	n100 int not null,
	n50 int not null,
	nmiss int not null,
	ngeki int not null,
	nkatu int not null,
	grade varchar(2) default 'N' not null,
	status tinyint not null,
	mode tinyint not null,
	play_time datetime not null,
	time_elapsed int not null,
	client_flags int not null,
	userid int not null,
	perfect tinyint(1) not null
);

create table scores_rx
(
	id bigint(20) unsigned auto_increment
		primary key,
	map_md5 char(32) not null,
	score int not null,
	pp float(7,3) not null,
	acc float(6,3) not null,
	max_combo int not null,
	mods int not null,
	n300 int not null,
	n100 int not null,
	n50 int not null,
	nmiss int not null,
	ngeki int not null,
	nkatu int not null,
	grade varchar(2) default 'N' not null,
	status tinyint not null,
	mode tinyint not null,
	play_time datetime not null,
	time_elapsed int not null,
	client_flags int not null,
	userid int not null,
	perfect tinyint(1) not null
);

create table scores_vn
(
	id bigint(20) unsigned auto_increment
		primary key,
	map_md5 char(32) not null,
	score int not null,
	pp float(7,3) not null,
	acc float(6,3) not null,
	max_combo int not null,
	mods int not null,
	n300 int not null,
	n100 int not null,
	n50 int not null,
	nmiss int not null,
	ngeki int not null,
	nkatu int not null,
	grade varchar(2) default 'N' not null,
	status tinyint not null,
	mode tinyint not null,
	play_time datetime not null,
	time_elapsed int not null,
	client_flags int not null,
	userid int not null,
	perfect tinyint(1) not null
);

create table startups
(
	id int auto_increment
		primary key,
	ver_major tinyint not null,
	ver_minor tinyint not null,
	ver_micro tinyint not null,
	datetime datetime not null
);

create table stats
(
	id int auto_increment
		primary key,
	tscore_vn_std bigint(21) unsigned default 0 not null,
	tscore_vn_taiko bigint(21) unsigned default 0 not null,
	tscore_vn_catch bigint(21) unsigned default 0 not null,
	tscore_vn_mania bigint(21) unsigned default 0 not null,
	tscore_rx_std bigint(21) unsigned default 0 not null,
	tscore_rx_taiko bigint(21) unsigned default 0 not null,
	tscore_rx_catch bigint(21) unsigned default 0 not null,
	tscore_ap_std bigint(21) unsigned default 0 not null,
	rscore_vn_std bigint(21) unsigned default 0 not null,
	rscore_vn_taiko bigint(21) unsigned default 0 not null,
	rscore_vn_catch bigint(21) unsigned default 0 not null,
	rscore_vn_mania bigint(21) unsigned default 0 not null,
	rscore_rx_std bigint(21) unsigned default 0 not null,
	rscore_rx_taiko bigint(21) unsigned default 0 not null,
	rscore_rx_catch bigint(21) unsigned default 0 not null,
	rscore_ap_std bigint(21) unsigned default 0 not null,
	pp_vn_std int(11) unsigned default 0 not null,
	pp_vn_taiko int(11) unsigned default 0 not null,
	pp_vn_catch int(11) unsigned default 0 not null,
	pp_vn_mania int(11) unsigned default 0 not null,
	pp_rx_std int(11) unsigned default 0 not null,
	pp_rx_taiko int(11) unsigned default 0 not null,
	pp_rx_catch int(11) unsigned default 0 not null,
	pp_ap_std int(11) unsigned default 0 not null,
	plays_vn_std int(11) unsigned default 0 not null,
	plays_vn_taiko int(11) unsigned default 0 not null,
	plays_vn_catch int(11) unsigned default 0 not null,
	plays_vn_mania int(11) unsigned default 0 not null,
	plays_rx_std int(11) unsigned default 0 not null,
	plays_rx_taiko int(11) unsigned default 0 not null,
	plays_rx_catch int(11) unsigned default 0 not null,
	plays_ap_std int(11) unsigned default 0 not null,
	playtime_vn_std int(11) unsigned default 0 not null,
	playtime_vn_taiko int(11) unsigned default 0 not null,
	playtime_vn_catch int(11) unsigned default 0 not null,
	playtime_vn_mania int(11) unsigned default 0 not null,
	playtime_rx_std int(11) unsigned default 0 not null,
	playtime_rx_taiko int(11) unsigned default 0 not null,
	playtime_rx_catch int(11) unsigned default 0 not null,
	playtime_ap_std int(11) unsigned default 0 not null,
	acc_vn_std float(6,3) default 0.000 not null,
	acc_vn_taiko float(6,3) default 0.000 not null,
	acc_vn_catch float(6,3) default 0.000 not null,
	acc_vn_mania float(6,3) default 0.000 not null,
	acc_rx_std float(6,3) default 0.000 not null,
	acc_rx_taiko float(6,3) default 0.000 not null,
	acc_rx_catch float(6,3) default 0.000 not null,
	acc_ap_std float(6,3) default 0.000 not null,
	maxcombo_vn_std int(11) unsigned default 0 not null,
	maxcombo_vn_taiko int(11) unsigned default 0 not null,
	maxcombo_vn_catch int(11) unsigned default 0 not null,
	maxcombo_vn_mania int(11) unsigned default 0 not null,
	maxcombo_rx_std int(11) unsigned default 0 not null,
	maxcombo_rx_taiko int(11) unsigned default 0 not null,
	maxcombo_rx_catch int(11) unsigned default 0 not null,
	maxcombo_ap_std int(11) unsigned default 0 not null
);

create table tourney_pool_maps
(
	map_id int not null,
	pool_id int not null,
	mods int not null,
	slot tinyint not null,
	primary key (map_id, pool_id)
);

create index tourney_pool_maps_tourney_pools_id_fk
	on tourney_pool_maps (pool_id);

create table tourney_pools
(
	id int auto_increment
		primary key,
	name varchar(16) not null,
	created_at datetime not null,
	created_by int not null
);

create index tourney_pools_users_id_fk
	on tourney_pools (created_by);

create table user_achievements
(
	userid int not null,
	achid int not null,
	primary key (userid, achid)
);

create table user_hashes
(
	id int auto_increment
		primary key,
	osupath char(32) not null,
	adapters char(32) not null,
	uninstall_id char(32) not null,
	disk_serial char(32) not null
);

create table users
(
	id int auto_increment
		primary key,
	name varchar(32) charset utf8 not null,
	safe_name varchar(32) charset utf8 not null,
	email varchar(254) not null,
	priv int default 1 not null,
	pw_bcrypt char(60) not null,
	country char(2) default 'xx' not null,
	silence_end int default 0 not null,
	donor_end int default 0 not null,
	creation_time int default 0 not null,
	latest_activity int default 0 not null,
	clan_id int default 0 not null,
	clan_priv tinyint(1) default 0 not null,
	api_key char(36) null,
	constraint users_api_key_uindex
		unique (api_key),
	constraint users_email_uindex
		unique (email),
	constraint users_name_uindex
		unique (name),
	constraint users_safe_name_uindex
		unique (safe_name)
);

insert into users (id, name, safe_name, priv, country, silence_end, email, pw_bcrypt, creation_time, latest_activity)
values (1, 'Aika', 'aika', 1, 'ca', 0, 'aika@gulag.ca',
        '_______________________my_cool_bcrypt_______________________', UNIX_TIMESTAMP(), UNIX_TIMESTAMP());

insert into stats (id) values (1);

# offset score ids to avoid replay file collisions.
alter table scores_rx auto_increment = 3074457345618258602;
alter table scores_ap auto_increment = 6148914691236517204;

# userid 2 is reserved for ppy in osu!, and the
# client will not allow users to pm this id.
# If you want this, simply remove these two lines.
alter table users auto_increment = 3;
alter table stats auto_increment = 3;

insert into channels (name, topic, read_priv, write_priv, auto_join)
values ('#osu', 'General discussion.', 1, 2, true),
	   ('#announce', 'Exemplary performance and public announcements.', 1, 24576, true),
	   ('#lobby', 'Multiplayer lobby discussion room.', 1, 2, false),
	   ('#supporter', 'General discussion for supporters.', 48, 48, false),
	   ('#staff', 'General discussion for staff members.', 28672, 28672, true),
	   ('#admin', 'General discussion for administrators.', 24576, 24576, true),
	   ('#dev', 'General discussion for developers.', 16384, 16384, true);

insert into achievements (id, file, name, `desc`, cond, mode) values (1, 'osu-skill-pass-1', 'Rising Star', 'Can''t go forward without the first steps.', '2 >= score.sr > 1', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (2, 'osu-skill-pass-2', 'Constellation Prize', 'Definitely not a consolation prize. Now things start getting hard!', '3 >= score.sr > 2', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (3, 'osu-skill-pass-3', 'Building Confidence', 'Oh, you''ve SO got this.', '(score.mods & 259 == 0) and 4 >= score.sr > 3', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (4, 'osu-skill-pass-4', 'Insanity Approaches', 'You''re not twitching, you''re just ready.', '5 >= score.sr > 4', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (5, 'osu-skill-pass-5', 'These Clarion Skies', 'Everything seems so clear now.', '6 >= score.sr > 5', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (6, 'osu-skill-pass-6', 'Above and Beyond', 'A cut above the rest.', '7 >= score.sr > 6', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (7, 'osu-skill-pass-7', 'Supremacy', 'All marvel before your prowess.', '8 >= score.sr > 7', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (8, 'osu-skill-pass-8', 'Absolution', 'My god, you''re full of stars!', '9 >= score.sr > 8', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (9, 'osu-skill-pass-9', 'Event Horizon', 'No force dares to pull you under.', '10 >= score.sr > 9', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (10, 'osu-skill-pass-10', 'Phantasm', 'Fevered is your passion, extraordinary is your skill.', '11 >= score.sr > 10', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (11, 'osu-skill-fc-1', 'Totality', 'All the notes. Every single one.', 'score.perfect and 2 >= score.sr > 1', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (12, 'osu-skill-fc-2', 'Business As Usual', 'Two to go, please.', 'score.perfect and 3 >= score.sr > 2', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (13, 'osu-skill-fc-3', 'Building Steam', 'Hey, this isn''t so bad.', 'score.perfect and 4 >= score.sr > 3', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (14, 'osu-skill-fc-4', 'Moving Forward', 'Bet you feel good about that.', 'score.perfect and 5 >= score.sr > 4', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (15, 'osu-skill-fc-5', 'Paradigm Shift', 'Surprisingly difficult.', 'score.perfect and 6 >= score.sr > 5', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (16, 'osu-skill-fc-6', 'Anguish Quelled', 'Don''t choke.', 'score.perfect and 7 >= score.sr > 6', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (17, 'osu-skill-fc-7', 'Never Give Up', 'Excellence is its own reward.', 'score.perfect and 8 >= score.sr > 7', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (18, 'osu-skill-fc-8', 'Aberration', 'They said it couldn''t be done. They were wrong.', 'score.perfect and 9 >= score.sr > 8', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (19, 'osu-skill-fc-9', 'Chosen', 'Reign among the Prometheans, where you belong.', 'score.perfect and 10 >= score.sr > 9', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (20, 'osu-skill-fc-10', 'Unfathomable', 'You have no equal.', 'score.perfect and 11 >= score.sr > 10', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (21, 'osu-combo-500', '500 Combo', '500 big ones! You''re moving up in the world!', '750 >= score.max_combo > 500', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (22, 'osu-combo-750', '750 Combo', '750 notes back to back? Woah.', '1000 >= score.max_combo > 750', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (23, 'osu-combo-1000', '1000 Combo', 'A thousand reasons why you rock at this game.', '2000 >= score.max_combo > 1000', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (24, 'osu-combo-2000', '2000 Combo', 'Nothing can stop you now.', 'score.max_combo >= 2000', 0);
insert into achievements (id, file, name, `desc`, cond, mode) values (25, 'taiko-skill-pass-1', 'My First Don', 'Marching to the beat of your own drum. Literally.', '2 >= score.sr > 1', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (26, 'taiko-skill-pass-2', 'Katsu Katsu Katsu', 'Hora! Izuko!', '3 >= score.sr > 2', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (27, 'taiko-skill-pass-3', 'Not Even Trying', 'Muzukashii? Not even.', '4 >= score.sr > 3', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (28, 'taiko-skill-pass-4', 'Face Your Demons', 'The first trials are now behind you, but are you a match for the Oni?', '5 >= score.sr > 4', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (29, 'taiko-skill-pass-5', 'The Demon Within', 'No rest for the wicked.', '6 >= score.sr > 5', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (30, 'taiko-skill-pass-6', 'Drumbreaker', 'Too strong.', '7 >= score.sr > 6', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (31, 'taiko-skill-pass-7', 'The Godfather', 'You are the Don of Dons.', '8 >= score.sr > 7', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (32, 'taiko-skill-pass-8', 'Rhythm Incarnate', 'Feel the beat. Become the beat.', '9 >= score.sr > 8', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (33, 'taiko-skill-fc-1', 'Keeping Time', 'Don, then katsu. Don, then katsu..', 'score.perfect and 2 >= score.sr > 1', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (34, 'taiko-skill-fc-2', 'To Your Own Beat', 'Straight and steady.', 'score.perfect and 3 >= score.sr > 2', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (35, 'taiko-skill-fc-3', 'Big Drums', 'Bigger scores to match.', 'score.perfect and 4 >= score.sr > 3', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (36, 'taiko-skill-fc-4', 'Adversity Overcome', 'Difficult? Not for you.', 'score.perfect and 5 >= score.sr > 4', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (37, 'taiko-skill-fc-5', 'Demonslayer', 'An Oni felled forevermore.', 'score.perfect and 6 >= score.sr > 5', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (38, 'taiko-skill-fc-6', 'Rhythm''s Call', 'Heralding true skill.', 'score.perfect and 7 >= score.sr > 6', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (39, 'taiko-skill-fc-7', 'Time Everlasting', 'Not a single beat escapes you.', 'score.perfect and 8 >= score.sr > 7', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (40, 'taiko-skill-fc-8', 'The Drummer''s Throne', 'Percussive brilliance befitting royalty alone.', 'score.perfect and 9 >= score.sr > 8', 1);
insert into achievements (id, file, name, `desc`, cond, mode) values (41, 'ctb-skill-pass-1', 'A Slice Of Life', 'Hey, this fruit catching business isn''t bad.', '2 >= score.sr > 1', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (42, 'ctb-skill-pass-2', 'Dashing Ever Forward', 'Fast is how you do it.', '3 >= score.sr > 2', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (43, 'ctb-skill-pass-3', 'Zesty Disposition', 'No scurvy for you, not with that much fruit.', '4 >= score.sr > 3', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (44, 'ctb-skill-pass-4', 'Hyperdash ON!', 'Time and distance is no obstacle to you.', '5 >= score.sr > 4', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (45, 'ctb-skill-pass-5', 'It''s Raining Fruit', 'And you can catch them all.', '6 >= score.sr > 5', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (46, 'ctb-skill-pass-6', 'Fruit Ninja', 'Legendary techniques.', '7 >= score.sr > 6', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (47, 'ctb-skill-pass-7', 'Dreamcatcher', 'No fruit, only dreams now.', '8 >= score.sr > 7', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (48, 'ctb-skill-pass-8', 'Lord of the Catch', 'Your kingdom kneels before you.', '9 >= score.sr > 8', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (49, 'ctb-skill-fc-1', 'Sweet And Sour', 'Apples and oranges, literally.', 'score.perfect and 2 >= score.sr > 1', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (50, 'ctb-skill-fc-2', 'Reaching The Core', 'The seeds of future success.', 'score.perfect and 3 >= score.sr > 2', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (51, 'ctb-skill-fc-3', 'Clean Platter', 'Clean only of failure. It is completely full, otherwise.', 'score.perfect and 4 >= score.sr > 3', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (52, 'ctb-skill-fc-4', 'Between The Rain', 'No umbrella needed.', 'score.perfect and 5 >= score.sr > 4', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (53, 'ctb-skill-fc-5', 'Addicted', 'That was an overdose?', 'score.perfect and 6 >= score.sr > 5', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (54, 'ctb-skill-fc-6', 'Quickening', 'A dash above normal limits.', 'score.perfect and 7 >= score.sr > 6', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (55, 'ctb-skill-fc-7', 'Supersonic', 'Faster than is reasonably necessary.', 'score.perfect and 8 >= score.sr > 7', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (56, 'ctb-skill-fc-8', 'Dashing Scarlet', 'Speed beyond mortal reckoning.', 'score.perfect and 9 >= score.sr > 8', 2);
insert into achievements (id, file, name, `desc`, cond, mode) values (57, 'mania-skill-pass-1', 'First Steps', 'It isn''t 9-to-5, but 1-to-9. Keys, that is.', '2 >= score.sr > 1', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (58, 'mania-skill-pass-2', 'No Normal Player', 'Not anymore, at least.', '3 >= score.sr > 2', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (59, 'mania-skill-pass-3', 'Impulse Drive', 'Not quite hyperspeed, but getting close.', '4 >= score.sr > 3', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (60, 'mania-skill-pass-4', 'Hyperspeed', 'Woah.', '5 >= score.sr > 4', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (61, 'mania-skill-pass-5', 'Ever Onwards', 'Another challenge is just around the corner.', '6 >= score.sr > 5', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (62, 'mania-skill-pass-6', 'Another Surpassed', 'Is there no limit to your skills?', '7 >= score.sr > 6', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (63, 'mania-skill-pass-7', 'Extra Credit', 'See me after class.', '8 >= score.sr > 7', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (64, 'mania-skill-pass-8', 'Maniac', 'There''s just no stopping you.', '9 >= score.sr > 8', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (65, 'mania-skill-fc-1', 'Keystruck', 'The beginning of a new story', 'score.perfect and 2 >= score.sr > 1', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (66, 'mania-skill-fc-2', 'Keying In', 'Finding your groove.', 'score.perfect and 3 >= score.sr > 2', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (67, 'mania-skill-fc-3', 'Hyperflow', 'You can *feel* the rhythm.', 'score.perfect and 4 >= score.sr > 3', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (68, 'mania-skill-fc-4', 'Breakthrough', 'Many skills mastered, rolled into one.', 'score.perfect and 5 >= score.sr > 4', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (69, 'mania-skill-fc-5', 'Everything Extra', 'Giving your all is giving everything you have.', 'score.perfect and 6 >= score.sr > 5', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (70, 'mania-skill-fc-6', 'Level Breaker', 'Finesse beyond reason', 'score.perfect and 7 >= score.sr > 6', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (71, 'mania-skill-fc-7', 'Step Up', 'A precipice rarely seen.', 'score.perfect and 8 >= score.sr > 7', 3);
insert into achievements (id, file, name, `desc`, cond, mode) values (72, 'mania-skill-fc-8', 'Behind The Veil', 'Supernatural!', 'score.perfect and 9 >= score.sr > 8', 3);
