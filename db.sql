create table users
(
	id int auto_increment
		primary key,
	name varchar(32) not null,
	name_safe varchar(32) not null,
	priv int null,
	pw_hash char(60) null,
	country char(2) default 'xx' not null,
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
	tscore_vn_std int not null,
	tscore_vn_taiko int not null,
	tscore_vn_catch int not null,
	tscore_vn_mania int not null,
	tscore_rx_std int not null,
	tscore_rx_taiko int not null,
	tscore_rx_catch int not null,
	rscore_vn_std int not null,
	rscore_vn_taiko int not null,
	rscore_vn_catch int not null,
	rscore_vn_mania int not null,
	rscore_rx_std int not null,
	rscore_rx_taiko int not null,
	rscore_rx_catch int not null,
	pp_vn_std smallint(6) not null,
	pp_vn_taiko smallint(6) not null,
	pp_vn_catch smallint(6) not null,
	pp_vn_mania smallint(6) not null,
	pp_rx_std smallint(6) not null,
	pp_rx_taiko smallint(6) not null,
	pp_rx_catch smallint(6) not null,
	playcount_vn_std int not null,
	playcount_vn_taiko int not null,
	playcount_vn_catch int not null,
	playcount_vn_mania int not null,
	playcount_rx_std int not null,
	playcount_rx_taiko int not null,
	playcount_rx_catch int not null,
	playtime_vn_std int not null,
	playtime_vn_taiko int not null,
	playtime_vn_catch int not null,
	playtime_vn_mania int not null,
	playtime_rx_std int not null,
	playtime_rx_taiko int not null,
	playtime_rx_catch int not null,
	acc_vn_std float(5,3) not null,
	acc_vn_taiko float(5,3) not null,
	acc_vn_catch float(5,3) not null,
	acc_vn_mania float(5,3) not null,
	acc_rx_std float(5,3) not null,
	acc_rx_taiko float(5,3) not null,
	acc_rx_catch float(5,3) not null,
	maxcombo_vn_std int not null,
	maxcombo_vn_taiko int not null,
	maxcombo_vn_catch int not null,
	maxcombo_vn_mania int not null,
	maxcombo_rx_std int not null,
	maxcombo_rx_taiko int not null,
	maxcombo_rx_catch int not null,
	constraint stats_users_id_fk
		foreign key (id) references users (id)
);
