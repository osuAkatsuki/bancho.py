# Remove pre-existing tables.
drop table if exists stats;
drop table if exists users;
drop table if exists client_hashes;
drop table if exists scores_rx;
drop table if exists scores_ap;
drop table if exists scores_vn;
drop table if exists maps;
drop table if exists friendships;
drop table if exists channels;
drop table if exists ratings;
drop table if exists performance_reports;
drop table if exists favourites;
drop table if exists comments;
drop table if exists mail;
drop table if exists logs;
drop table if exists tourney_pools;
drop table if exists tourney_pool_maps;

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
	constraint users_email_uindex
		unique (email),
	constraint users_safe_name_uindex
		unique (safe_name),
	constraint users_name_uindex
		unique (name)
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

# with this i decided to make a naming scheme rather
# than something nescessarily 'readable' or pretty, i
# think in practice this will be much easier to use
# and memorize quickly compared to other schemes.
# the syntax is simply: stat_rxmode_osumode
create table stats
(
	id int auto_increment
		primary key,
	tscore_vn_std int default 0 not null,
	tscore_vn_taiko int default 0 not null,
	tscore_vn_catch int default 0 not null,
	tscore_vn_mania int default 0 not null,
	tscore_rx_std int default 0 not null,
	tscore_rx_taiko int default 0 not null,
	tscore_rx_catch int default 0 not null,
	tscore_ap_std int default 0 not null,
	rscore_vn_std int default 0 not null,
	rscore_vn_taiko int default 0 not null,
	rscore_vn_catch int default 0 not null,
	rscore_vn_mania int default 0 not null,
	rscore_rx_std int default 0 not null,
	rscore_rx_taiko int default 0 not null,
	rscore_rx_catch int default 0 not null,
	rscore_ap_std int default 0 not null,
	pp_vn_std smallint(6) default 0 not null,
	pp_vn_taiko smallint(6) default 0 not null,
	pp_vn_catch smallint(6) default 0 not null,
	pp_vn_mania smallint(6) default 0 not null,
	pp_rx_std smallint(6) default 0 not null,
	pp_rx_taiko smallint(6) default 0 not null,
	pp_rx_catch smallint(6) default 0 not null,
	pp_ap_std smallint(6) default 0 not null,
	plays_vn_std int default 0 not null,
	plays_vn_taiko int default 0 not null,
	plays_vn_catch int default 0 not null,
	plays_vn_mania int default 0 not null,
	plays_rx_std int default 0 not null,
	plays_rx_taiko int default 0 not null,
	plays_rx_catch int default 0 not null,
	plays_ap_std int default 0 not null,
	playtime_vn_std int default 0 not null,
	playtime_vn_taiko int default 0 not null,
	playtime_vn_catch int default 0 not null,
	playtime_vn_mania int default 0 not null,
	playtime_rx_std int default 0 not null,
	playtime_rx_taiko int default 0 not null,
	playtime_rx_catch int default 0 not null,
	playtime_ap_std int default 0 not null,
	acc_vn_std float(6,3) default 0.000 not null,
	acc_vn_taiko float(6,3) default 0.000 not null,
	acc_vn_catch float(6,3) default 0.000 not null,
	acc_vn_mania float(6,3) default 0.000 not null,
	acc_rx_std float(6,3) default 0.000 not null,
	acc_rx_taiko float(6,3) default 0.000 not null,
	acc_rx_catch float(6,3) default 0.000 not null,
	acc_ap_std float(6,3) default 0.000 not null,
	maxcombo_vn_std int default 0 not null,
	maxcombo_vn_taiko int default 0 not null,
	maxcombo_vn_catch int default 0 not null,
	maxcombo_vn_mania int default 0 not null,
	maxcombo_rx_std int default 0 not null,
	maxcombo_rx_taiko int default 0 not null,
	maxcombo_rx_catch int default 0 not null,
	maxcombo_ap_std int default 0 not null,
	constraint stats_users_id_fk
		foreign key (id) references users (id)
			on update cascade on delete cascade
);

create table scores_rx
(
	id int auto_increment
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

create table scores_ap
(
	id int auto_increment
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
	id int auto_increment
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

create table maps
(
	server enum('osu!', 'gulag') default 'osu!' not null,
	id int not null,
	set_id int not null,
	status int not null,
	md5 char(32) not null,
	artist varchar(128) not null,
	title varchar(128) not null,
	version varchar(128) not null,
	creator varchar(19) not null comment 'not 100% certain on len',
	last_update datetime not null,
	total_length int not null,
	frozen tinyint(1) default 0 not null,
	plays int default 0 not null,
	passes int default 0 not null,
	mode tinyint(1) default 0 not null,
	bpm float(9,2) default 0.00 not null,
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

create table friendships
(
	user1 int not null,
	user2 int not null,
	primary key (user1, user2)
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

create table ratings
(
	userid int not null,
	map_md5 char(32) not null,
	rating tinyint(2) not null,
	primary key (userid, map_md5),
	constraint ratings_map_md5_uindex
		unique (map_md5),
	constraint ratings_userid_uindex
		unique (userid),
	constraint ratings_maps_md5_fk
		foreign key (map_md5) references maps (md5)
			on update cascade on delete cascade,
	constraint ratings_users_id_fk
		foreign key (userid) references users (id)
			on update cascade on delete cascade
);

create table performance_reports
(
	scoreid int not null
		primary key,
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
	average_frametime int not null
);

create table favourites
(
	userid int not null,
	setid int not null,
	primary key (userid, setid)
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

create table logs
(
	id int auto_increment
		primary key,
	`from` int not null comment 'both from and to are playerids',
	`to` int not null,
	msg varchar(2048) charset utf8 not null,
	time datetime not null on update CURRENT_TIMESTAMP
);

create table tourney_pools
(
	id int auto_increment
		primary key,
	name varchar(16) not null,
	created_at datetime not null,
	created_by int not null,
	constraint tourney_pools_users_id_fk
		foreign key (created_by) references users (id)
);

create table tourney_pool_maps
(
	map_id int not null,
	pool_id int not null,
	mods int not null,
	slot tinyint not null,
	primary key (map_id, pool_id),
	constraint tourney_pool_maps_tourney_pools_id_fk
		foreign key (pool_id) references tourney_pools (id)
			on update cascade on delete cascade
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

# insert vital stuff, such as bot user & basic channels.

insert into users (id, name, safe_name, priv, country, silence_end, email, pw_bcrypt, creation_time, latest_activity)
values (1, 'Aika', 'aika', 1, 'ca', 0, 'aika@gulag.ca',
        '_______________________my_cool_bcrypt_______________________', UNIX_TIMESTAMP(), UNIX_TIMESTAMP());

insert into stats (id) values (1);

# userid 2 is reserved for ppy in osu!, and the
# client will not allow users to pm this id.
# If you want this, simply remove these two lines.
alter table users auto_increment = 3;
alter table stats auto_increment = 3;

insert into channels (name, topic, read_priv, write_priv, auto_join)
values ('#osu', 'General discussion.', 1, 2, true),
	   ('#announce', 'Exemplary performance and public announcements.', 1, 2, true),
	   ('#lobby', 'Multiplayer lobby discussion room.', 1, 2, false),
	   ('#supporter', 'General discussion for p2w gamers.', 48, 48, false),
	   ('#staff', 'General discussion for the cool kids.', 28672, 28672, true),
	   ('#admin', 'General discussion for the cool.', 24576, 24576, true),
	   ('#dev',   'General discussion for the.', 16384, 16384, true);
