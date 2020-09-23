# Remove pre-existing tables.
drop table if exists stats;
drop table if exists users;
drop table if exists scores_rx;
drop table if exists scores_vn;
drop table if exists maps;
drop table if exists friendships;
drop table if exists channels;

create table users
(
	id int auto_increment
		primary key,
	name varchar(32) not null,
	name_safe varchar(32) not null,
	priv int default 1 null,
	pw_hash char(60) null,
	country char(2) default 'xx' not null,
	silence_end int default 0 not null,
	email varchar(254) not null,
	constraint users_email_uindex
		unique (email),
	constraint users_name_safe_uindex
		unique (name_safe),
	constraint users_name_uindex
		unique (name)
);

create table user_hashes
(
	id int auto_increment
		primary key,
	osupath char(32) not null,
	adapters char(32) not null,
	uninstall_id char(32) not null,
	disk_serial char(32) not null,
	constraint user_hashes_users_id_fk
		foreign key (id) references users (id)
			on update cascade on delete cascade
);

# With this I decided to make a naming scheme rather
# than something nescessarily 'readable' or pretty, I
# think in practice this will be much easier to use
# and memorize quickly compared to other schemes.
# Syntax is simply: stat_rxmode_osumode
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
	rscore_vn_std int default 0 not null,
	rscore_vn_taiko int default 0 not null,
	rscore_vn_catch int default 0 not null,
	rscore_vn_mania int default 0 not null,
	rscore_rx_std int default 0 not null,
	rscore_rx_taiko int default 0 not null,
	rscore_rx_catch int default 0 not null,
	pp_vn_std smallint(6) default 0 not null,
	pp_vn_taiko smallint(6) default 0 not null,
	pp_vn_catch smallint(6) default 0 not null,
	pp_vn_mania smallint(6) default 0 not null,
	pp_rx_std smallint(6) default 0 not null,
	pp_rx_taiko smallint(6) default 0 not null,
	pp_rx_catch smallint(6) default 0 not null,
	plays_vn_std int default 0 not null,
	plays_vn_taiko int default 0 not null,
	plays_vn_catch int default 0 not null,
	plays_vn_mania int default 0 not null,
	plays_rx_std int default 0 not null,
	plays_rx_taiko int default 0 not null,
	plays_rx_catch int default 0 not null,
	playtime_vn_std int default 0 not null,
	playtime_vn_taiko int default 0 not null,
	playtime_vn_catch int default 0 not null,
	playtime_vn_mania int default 0 not null,
	playtime_rx_std int default 0 not null,
	playtime_rx_taiko int default 0 not null,
	playtime_rx_catch int default 0 not null,
	acc_vn_std float(5,3) default 0.000 not null,
	acc_vn_taiko float(5,3) default 0.000 not null,
	acc_vn_catch float(5,3) default 0.000 not null,
	acc_vn_mania float(5,3) default 0.000 not null,
	acc_rx_std float(5,3) default 0.000 not null,
	acc_rx_taiko float(5,3) default 0.000 not null,
	acc_rx_catch float(5,3) default 0.000 not null,
	maxcombo_vn_std int default 0 not null,
	maxcombo_vn_taiko int default 0 not null,
	maxcombo_vn_catch int default 0 not null,
	maxcombo_vn_mania int default 0 not null,
	maxcombo_rx_std int default 0 not null,
	maxcombo_rx_taiko int default 0 not null,
	maxcombo_rx_catch int default 0 not null,
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
	game_mode tinyint not null,
	play_time int not null,
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
	game_mode tinyint not null,
	play_time int not null,
	time_elapsed int not null,
	client_flags int not null,
	userid int not null,
	perfect tinyint(1) not null
);

# TODO: find the real max lengths for strings
create table maps
(
	id int not null
	    primary key,
	set_id int not null,
	status int not null,
	md5 char(32) not null,
	artist varchar(128) not null,
	title varchar(128) not null,
	version varchar(128) not null,
	creator varchar(128) not null,
	last_update datetime null comment 'will be NOT NULL in future',
	frozen tinyint(1) default 0 null,
	plays int default 0 not null,
	passes int default 0 not null,
	mode tinyint(1) default 0 not null,
	bpm float(9,2) default 0.00 not null,
	cs float(4,2) default 0.00 not null,
	ar float(4,2) default 0.00 not null,
	od float(4,2) default 0.00 not null,
	hp float(4,2) default 0.00 not null,
	diff float(6,3) default 0.000 not null,
	constraint maps_id_uindex
		unique (id),
	constraint maps_md5_uindex
		unique (md5)
);

create table friendships
(
  	user1 int(11) not null,
	user2 int(11) not null,
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
	auto_join tinyint(1) default 0 null,
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
	fps_cap int null,
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

# Insert vital stuff, such as bot user & basic channels.

insert into users (id, name, name_safe, priv, country, silence_end, email, pw_hash)
values (1, 'Aika', 'aika', 1, 'ca', 0, 'aika@gulag.ca',
        '_______________________my_cool_bcrypt_______________________');

insert into stats (id) values (1);

# userid 2 is reserved for ppy in osu!, and the
# client will not allow users to pm this id.
# If you want this, simply remove these two lines.
alter table users auto_increment = 3;
alter table stats auto_increment = 3;

insert into channels (name, topic, read_priv, write_priv, auto_join)
values ('#osu', 'General discussion.', 1, 2, true),
	   ('#announce', 'Exemplary performance and public announcements.', 1, 2, true),
	   ('#lobby', 'Multiplayer lobby discussion room.', 1, 2, false);
