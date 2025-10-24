create table achievements
(
	id int auto_increment
		primary key,
	file varchar(128) not null,
	name varchar(128) charset utf8 not null,
	`desc` varchar(256) charset utf8 not null,
	cond varchar(64) not null,
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
create index channels_auto_join_index
	on channels (auto_join);
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
	created_at int default 0 not null,
	primary key (userid, setid)
);
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
create table relationships
(
	user1 int not null,
	user2 int not null,
	type enum('friend', 'block') not null,
	primary key (user1, user2)
);
create table logs
(
	id int auto_increment
		primary key,
	`from` int not null comment 'both from and to are playerids',
	`to` int not null,
	`action` varchar(32) not null,
	msg varchar(2048) charset utf8 null,
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
	server enum('osu!', 'private') default 'osu!' not null,
	id int not null,
	set_id int not null,
	status int not null,
	md5 char(32) not null,
	artist varchar(128) charset utf8 not null,
	title varchar(128) charset utf8 not null,
	version varchar(128) charset utf8 not null,
	creator varchar(19) charset utf8 not null,
	filename varchar(256) charset utf8 not null,
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
create index maps_set_id_index
	on maps (set_id);
create index maps_status_index
	on maps (status);
create index maps_filename_index
	on maps (filename);
create index maps_plays_index
	on maps (plays);
create index maps_mode_index
	on maps (mode);
create index maps_frozen_index
	on maps (frozen);
create table mapsets
(
	server enum('osu!', 'private') default 'osu!' not null,
	id int not null,
	last_osuapi_check datetime default CURRENT_TIMESTAMP not null,
	primary key (server, id),
	constraint nmapsets_id_uindex
		unique (id)
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
	primary key (userid, map_md5)
);
create table scores
(
	id bigint unsigned auto_increment
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
	perfect tinyint(1) not null,
	online_checksum char(32) not null
);
create index scores_map_md5_index
	on scores (map_md5);
create index scores_score_index
	on scores (score);
create index scores_pp_index
	on scores (pp);
create index scores_mods_index
	on scores (mods);
create index scores_status_index
	on scores (status);
create index scores_mode_index
	on scores (mode);
create index scores_play_time_index
	on scores (play_time);
create index scores_userid_index
	on scores (userid);
create index scores_online_checksum_index
	on scores (online_checksum);
create index scores_fetch_leaderboard_generic_index
	on scores (map_md5, status, mode);
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
	id int auto_increment,
	mode tinyint(1) not null,
	tscore bigint unsigned default 0 not null,
	rscore bigint unsigned default 0 not null,
	pp int unsigned default 0 not null,
	pp_total int unsigned default 0 not null,
	pp_stddev int unsigned default 0 not null,
	plays int unsigned default 0 not null,
	playtime int unsigned default 0 not null,
	acc float(6,3) default 0.000 not null,
	max_combo int unsigned default 0 not null,
	total_hits int unsigned default 0 not null,
	replay_views int unsigned default 0 not null,
	xh_count int unsigned default 0 not null,
	x_count int unsigned default 0 not null,
	sh_count int unsigned default 0 not null,
	s_count int unsigned default 0 not null,
	a_count int unsigned default 0 not null,
	primary key (id, mode)
);
create index stats_mode_index
	on stats (mode);
create index stats_pp_index
	on stats (pp);
create index stats_tscore_index
	on stats (tscore);
create index stats_rscore_index
	on stats (rscore);
create table tourney_pool_maps
(
	map_id int not null,
	pool_id int not null,
	mods int not null,
	slot tinyint not null,
	primary key (map_id, pool_id)
);
create index tourney_pool_maps_mods_slot_index
	on tourney_pool_maps (mods, slot);
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
create index user_achievements_achid_index
	on user_achievements (achid);
create index user_achievements_userid_index
	on user_achievements (userid);
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
	preferred_mode int default 0 not null,
	play_style int default 0 not null,
	custom_badge_name varchar(16) charset utf8 null,
	custom_badge_icon varchar(64) null,
	userpage_content varchar(2048) charset utf8 null,
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
create index users_priv_index
	on users (priv);
create index users_clan_id_index
	on users (clan_id);
create index users_clan_priv_index
	on users (clan_priv);
create index users_country_index
	on users (country);
insert into users (id, name, safe_name, priv, country, silence_end, email, pw_bcrypt, creation_time, latest_activity)
values (1, 'BanchoBot', 'banchobot', 1, 'ca', 0, 'bot@akatsuki.pw',
        '_______________________my_cool_bcrypt_______________________', UNIX_TIMESTAMP(), UNIX_TIMESTAMP());
INSERT INTO stats (id, mode) VALUES (1, 0); # vn!std
INSERT INTO stats (id, mode) VALUES (1, 1); # vn!taiko
INSERT INTO stats (id, mode) VALUES (1, 2); # vn!catch
INSERT INTO stats (id, mode) VALUES (1, 3); # vn!mania
INSERT INTO stats (id, mode) VALUES (1, 4); # rx!std
INSERT INTO stats (id, mode) VALUES (1, 5); # rx!taiko
INSERT INTO stats (id, mode) VALUES (1, 6); # rx!catch
INSERT INTO stats (id, mode) VALUES (1, 8); # ap!std
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
insert into achievements (id, file, name, `desc`, cond) values (1, 'osu-skill-pass-1', 'Rising Star', 'Can''t go forward without the first steps.', '(score.mods & 1 == 0) and 1 <= score.sr < 2 and mode_vn == 0');
