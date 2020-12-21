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
