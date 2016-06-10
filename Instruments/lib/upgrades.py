##
## code to upgrade sql schema / etc

sqlcode = {}

# version 1.2 --
#  makes position (name, instrument_id) unique

sqlcode['1.2'] = [
    "begin transaction",
    """create temporary table position_backup(
    id INTEGER NOT NULL,  name TEXT NOT NULL,
    notes TEXT, attributes TEXT, date DATETIME,
    instrument_id INTEGER,
    PRIMARY KEY (id),
    FOREIGN KEY(instrument_id) REFERENCES instrument (id))""",
    "insert into position_backup SELECT * from position",
    "drop table position",
    """create table position(
    id INTEGER NOT NULL,  name TEXT NOT NULL,
    notes TEXT,  attributes TEXT,  date DATETIME,
    instrument_id INTEGER,
    unique(name, instrument_id),
    PRIMARY KEY (id),
    FOREIGN KEY(instrument_id) REFERENCES instrument (id))""",
    "insert into position SELECT * from position_backup",
    "drop table position_backup"]

# version 1.3 adds "move order" to instruments to allow
# controlling of the order that PVs are moved.
sqlcode['1.3'] = ["alter table instrument_pv add column move_order integer;",
                  "update instrument_pv set move_order=1;",
                  ]
