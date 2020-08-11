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

-- With this I decided to make a naming scheme rather
-- than something nescessarily 'readable' or pretty, I
-- think in practice this will be much easier to use
-- and memorize quickly compared to other schemes.
-- Syntax is simply: stat_rxmode_osumode
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
	status tinyint not null,
	game_mode tinyint not null,
	play_time int not null,
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
	status tinyint not null,
	game_mode tinyint not null,
	play_time int not null,
	client_flags int not null,
	userid int not null,
	perfect tinyint(1) not null
);

create table maps
(
	id int not null
	    primary key,
	set_id int not null,
	status int not null,
	name varchar(256) not null comment 'Unsure of max length',
	md5 char(32) not null,
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
	auto_join tinyint(1) default 0 null,
	constraint channels_name_uindex
		unique (name)
);

-- Insert vital stuff, such as bot user & basic channels.

insert into cmyui.users (id, name, name_safe, priv, country, silence_end, email, pw_hash)
values (1, 'Aika', 'aika', 1, 'ca', 0, 'aika@gulag.ca',
        '_______________________my_cool_bcrypt_______________________');

insert into cmyui.stats (id) values (1);

insert into channels (name, topic, read_priv, write_priv, auto_join)
values
	('#osu', 'General discussion.', 1, 2, true),
	('#announce', 'Exemplary performance and public announcements.', 1, 2, true),
	('#lobby', 'Multiplayer lobby discussion room.', 1, 2, false);
