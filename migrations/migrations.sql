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
alter table stats modify tscore_vn_std int unsigned default 0 not null;
alter table stats modify tscore_vn_taiko int unsigned default 0 not null;
alter table stats modify tscore_vn_catch int unsigned default 0 not null;
alter table stats modify tscore_vn_mania int unsigned default 0 not null;
alter table stats modify tscore_rx_std int unsigned default 0 not null;
alter table stats modify tscore_rx_taiko int unsigned default 0 not null;
alter table stats modify tscore_rx_catch int unsigned default 0 not null;
alter table stats modify tscore_ap_std int unsigned default 0 not null;

alter table stats modify rscore_vn_std int unsigned default 0 not null;
alter table stats modify rscore_vn_taiko int unsigned default 0 not null;
alter table stats modify rscore_vn_catch int unsigned default 0 not null;
alter table stats modify rscore_vn_mania int unsigned default 0 not null;
alter table stats modify rscore_rx_std int unsigned default 0 not null;
alter table stats modify rscore_rx_taiko int unsigned default 0 not null;
alter table stats modify rscore_rx_catch int unsigned default 0 not null;
alter table stats modify rscore_ap_std int unsigned default 0 not null;

alter table stats modify pp_vn_std smallint unsigned default 0 not null;
alter table stats modify pp_vn_taiko smallint unsigned default 0 not null;
alter table stats modify pp_vn_catch smallint unsigned default 0 not null;
alter table stats modify pp_vn_mania smallint unsigned default 0 not null;
alter table stats modify pp_rx_std smallint unsigned default 0 not null;
alter table stats modify pp_rx_taiko smallint unsigned default 0 not null;
alter table stats modify pp_rx_catch smallint unsigned default 0 not null;
alter table stats modify pp_ap_std smallint unsigned default 0 not null;

alter table stats modify plays_vn_std int unsigned default 0 not null;
alter table stats modify plays_vn_taiko int unsigned default 0 not null;
alter table stats modify plays_vn_catch int unsigned default 0 not null;
alter table stats modify plays_vn_mania int unsigned default 0 not null;
alter table stats modify plays_rx_std int unsigned default 0 not null;
alter table stats modify plays_rx_taiko int unsigned default 0 not null;
alter table stats modify plays_rx_catch int unsigned default 0 not null;
alter table stats modify plays_ap_std int unsigned default 0 not null;

alter table stats modify playtime_vn_std int unsigned default 0 not null;
alter table stats modify playtime_vn_taiko int unsigned default 0 not null;
alter table stats modify playtime_vn_catch int unsigned default 0 not null;
alter table stats modify playtime_vn_mania int unsigned default 0 not null;
alter table stats modify playtime_rx_std int unsigned default 0 not null;
alter table stats modify playtime_rx_taiko int unsigned default 0 not null;
alter table stats modify playtime_rx_catch int unsigned default 0 not null;
alter table stats modify playtime_ap_std int unsigned default 0 not null;

alter table stats modify maxcombo_vn_std int unsigned default 0 not null;
alter table stats modify maxcombo_vn_taiko int unsigned default 0 not null;
alter table stats modify maxcombo_vn_catch int unsigned default 0 not null;
alter table stats modify maxcombo_vn_mania int unsigned default 0 not null;
alter table stats modify maxcombo_rx_std int unsigned default 0 not null;
alter table stats modify maxcombo_rx_taiko int unsigned default 0 not null;
alter table stats modify maxcombo_rx_catch int unsigned default 0 not null;
alter table stats modify maxcombo_ap_std int unsigned default 0 not null;

alter table stats modify acc_vn_std float(6, 3) default 0.000 not null;
alter table stats modify acc_vn_taiko float(6, 3) default 0.000 not null;
alter table stats modify acc_vn_catch float(6, 3) default 0.000 not null;
alter table stats modify acc_vn_mania float(6, 3) default 0.000 not null;
alter table stats modify acc_rx_std float(6, 3) default 0.000 not null;
alter table stats modify acc_rx_taiko float(6, 3) default 0.000 not null;
alter table stats modify acc_rx_catch float(6, 3) default 0.000 not null;
alter table stats modify acc_ap_std float(6, 3) default 0.000 not null;

# v4.7.1
lock tables maps write;
alter table maps drop primary key;
alter table maps add primary key (id);
alter table maps modify column server enum('osu!', 'private') not null default 'osu!' after id;
unlock tables;

# v5.0.1
create index channels_auto_join_index
	on channels (auto_join);

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

create index stats_mode_index
	on stats (mode);

create index stats_pp_index
	on stats (pp);

create index stats_tscore_index
	on stats (tscore);

create index stats_rscore_index
	on stats (rscore);

create index tourney_pool_maps_mods_slot_index
	on tourney_pool_maps (mods, slot);

create index user_achievements_achid_index
	on user_achievements (achid);

create index user_achievements_userid_index
	on user_achievements (userid);

create index users_priv_index
	on users (priv);

create index users_clan_id_index
	on users (clan_id);

create index users_clan_priv_index
	on users (clan_priv);

create index users_country_index
	on users (country);

# v5.2.2
create index scores_fetch_leaderboard_generic_index
	on scores (map_md5, status, mode);

# v5.2.X
alter table stats add column pp_total int unsigned default 0 not null after pp;
alter table stats add column pp_stddev int unsigned default 0 not null after pp_total;
alter table stats add index stats_total_pp_index (pp_total);
alter table stats add index stats_stddev_pp_index (pp_stddev);
