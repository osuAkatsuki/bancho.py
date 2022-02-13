package main

import (
	_ "github.com/go-sql-driver/mysql"
	"github.com/jmoiron/sqlx"

	"database/sql"
	"sync/atomic"

	"fmt"
	"os"
	"reflect"
	"strings"
	"sync"
	"time"
)

/// MIGRATIONS INSTRUCTIONS ///
// first install golang & dependencies
// $ apt install golang
// $ go get github.com/go-sql-driver/mysql
// $ go get github.com/jmoiron/sqlx

// next, configure these parameters
var SQLUsername string = "cmyui"
var SQLPassword string = "lol123"
var SQLDatabase string = "gulag_old"
var SQLHost string = "127.0.0.1"
var SQLPort string = "3306"
var GulagPath string = "/home/cmyui/programming/gulag" // NOTE: no trailing slash!

// then, build & run the binary
// $ go run .

var DB *sqlx.DB

type Score struct {
	ID             int64
	MapMD5         string `db:"map_md5"`
	Score          int
	PP             float32
	Acc            float32
	MaxCombo       int `db:"max_combo"`
	Mods           int
	N300           int
	N100           int
	N50            int
	Nmiss          int
	Ngeki          int
	Nkatu          int
	Grade          string
	Status         int
	Mode           int
	PlayTime       int64 `db:"play_time"`
	TimeElapsed    int   `db:"time_elapsed"`
	ClientFlags    int   `db:"client_flags"`
	UserID         int64 `db:"userid"`
	Perfect        int
	OnlineChecksum sql.NullString `db:"online_checksum"`
}

var create_scores = `
create table scores (
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
	online_checksum char(32) not null default ''
);
`

var insert_score = `
INSERT INTO scores VALUES (
    NULL,
    :map_md5,
    :score,
    :pp,
    :acc,
    :max_combo,
    :mods,
    :n300,
    :n100,
    :n50,
    :nmiss,
    :ngeki,
    :nkatu,
    :grade,
    :status,
    :mode,
    FROM_UNIXTIME(:play_time),
    :time_elapsed,
    :client_flags,
    :userid,
    :perfect,
    :online_checksum
)`

var replaysMoved int32

func recalculate_chunk(chunk []Score, table string, increase int) {
	tx := DB.MustBegin()
	batch := 1

	for _, score := range chunk {
		score.Mode += increase

		if batch == 0 {
			tx = DB.MustBegin()
		}
		batch++

		if !score.OnlineChecksum.Valid {
			score.OnlineChecksum.String = ""
			score.OnlineChecksum.Valid = true
		}

		res, err := tx.NamedExec(insert_score, &score)
		if err != nil {
			fmt.Println(err)
			continue
		}

		new_id, err := res.LastInsertId()
		if err != nil {
			fmt.Println(err)
			continue
		}

		if score.Status != 0 {
			// this is a submitted score, move the replay file as well
			oldReplayPath := fmt.Sprintf("/tmp/gulag_replays/%d.osr", score.ID)
			if _, err := os.Stat(oldReplayPath); os.IsNotExist(err) {
				fmt.Printf("Warning: replay file for old ID %d could not be found\n", score.ID)
			} else {
				newReplayPath := fmt.Sprintf("%s/.data/osr/%d.osr", GulagPath, new_id)
				os.Rename(oldReplayPath, newReplayPath)
				atomic.AddInt32(&replaysMoved, 1)
			}
		}

		if batch == 3000 {
			batch = 0
			tx.Commit()
		}
	}

	if batch != 0 {
		tx.Commit()
	}
}

func SplitToChunks(slice interface{}, chunkSize int) interface{} {
	sliceType := reflect.TypeOf(slice)
	sliceVal := reflect.ValueOf(slice)
	length := sliceVal.Len()
	if sliceType.Kind() != reflect.Slice {
		panic("parameter must be []T")
	}
	n := 0
	if length%chunkSize > 0 {
		n = 1
	}
	SST := reflect.MakeSlice(reflect.SliceOf(sliceType), 0, length/chunkSize+n)
	st, ed := 0, 0
	for st < length {
		ed = st + chunkSize
		if ed > length {
			ed = length
		}
		SST = reflect.Append(SST, sliceVal.Slice(st, ed))
		st = ed
	}
	return SST.Interface()
}

func main() {
	if _, err := os.Stat(GulagPath); os.IsNotExist(err) {
		panic("Gulag path is invalid")
	}

	db, err := sqlx.Open("mysql", fmt.Sprintf("%s:%s@(%s:%s)/%s", SQLUsername, SQLPassword, SQLHost, SQLPort, SQLDatabase))
	if err != nil {
		panic(err)
	}

	err = os.Rename(fmt.Sprintf("%s/.data/osr", GulagPath), "/tmp/gulag_replays")
	if err != nil {
		panic(err)
	}

	err = os.Mkdir(fmt.Sprintf("%s/.data/osr", GulagPath), 0755)
	if err != nil {
		panic(err)
	}

	DB = db
	var wg sync.WaitGroup

	DB.MustExec(create_scores)
	start := time.Now()

	vn_scores := []Score{}
	vn_rows, err := DB.Queryx(`
	SELECT id, map_md5, score, pp, acc, max_combo, mods, n300, n100,
	n50, nmiss, ngeki, nkatu, grade, status, mode, UNIX_TIMESTAMP(play_time) AS play_time,
	time_elapsed, client_flags, userid, perfect, online_checksum FROM scores_vn`)
	if err != nil {
		panic(err)
	}

	for vn_rows.Next() {
		score := Score{}
		err := vn_rows.StructScan(&score)
		if err != nil {
			panic(err)
		}

		vn_scores = append(vn_scores, score)
	}

	for _, vn_chunk := range SplitToChunks(vn_scores, 10000).([][]Score) {
		wg.Add(1)
		go func(chunk []Score) {
			defer wg.Done()
			recalculate_chunk(chunk, "scores_vn", 0)
		}(vn_chunk)
	}

	rx_scores := []Score{}
	rx_rows, err := DB.Queryx(`
	SELECT id, map_md5, score, pp, acc, max_combo, mods, n300, n100,
	n50, nmiss, ngeki, nkatu, grade, status, mode, UNIX_TIMESTAMP(play_time) AS play_time,
	time_elapsed, client_flags, userid, perfect, online_checksum FROM scores_rx`)
	if err != nil {
		panic(err)
	}

	for rx_rows.Next() {
		score := Score{}
		err := rx_rows.StructScan(&score)
		if err != nil {
			panic(err)
		}

		rx_scores = append(rx_scores, score)
	}

	for _, rx_chunk := range SplitToChunks(rx_scores, 10000).([][]Score) {
		wg.Add(1)
		go func(chunk []Score) {
			defer wg.Done()
			recalculate_chunk(chunk, "scores_rx", 4)
		}(rx_chunk)
	}

	ap_scores := []Score{}
	ap_rows, err := DB.Queryx(`
	SELECT id, map_md5, score, pp, acc, max_combo, mods, n300, n100,
	n50, nmiss, ngeki, nkatu, grade, status, mode, UNIX_TIMESTAMP(play_time) AS play_time,
	time_elapsed, client_flags, userid, perfect, online_checksum FROM scores_ap`)
	if err != nil {
		panic(err)
	}

	for ap_rows.Next() {
		score := Score{}
		err := ap_rows.StructScan(&score)
		if err != nil {
			panic(err)
		}

		ap_scores = append(ap_scores, score)
	}

	for _, ap_chunk := range SplitToChunks(ap_scores, 10000).([][]Score) {
		wg.Add(1)
		go func(chunk []Score) {
			defer wg.Done()
			recalculate_chunk(chunk, "scores_ap", 8)
		}(ap_chunk)
	}

	wg.Wait()

	err = os.Remove("/tmp/gulag_replays")
	if err != nil {
		fmt.Println("There are some replays files for which scores could not be found in the database. They have been left at /tmp/gulag_replays.")
	}

	elapsed := time.Since(start)
	fmt.Printf("Score migrator took %s\n", elapsed)
	fmt.Printf("Moved %d replays\n", replaysMoved)

	fmt.Printf("Do you wish to drop the old tables? (y/n)\n>> ")
	var res string
	fmt.Scanln(&res)
	res = strings.ToLower(res)

	if res == "y" {
		fmt.Println("Dropping old tables")
		DB.MustExec("drop table scores_vn")
		DB.MustExec("drop table scores_rx")
		DB.MustExec("drop table scores_ap")
	} else {
		fmt.Println("Not dropping old tables")
	}
}
