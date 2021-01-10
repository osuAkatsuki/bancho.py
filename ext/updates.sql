# This file contains any sql updates, along with the
# version they are required from. Touching this without
# atleast reading utils/updater.py is certainly a bad idea :)

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
