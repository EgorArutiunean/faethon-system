"""Read-only reader for an InterBase 7 / ODS 11 .GDB file.

Firebird rejects this file even when the ODS number matches, because it is an
InterBase database (the Firebird ODS flag is clear). InterBase 2020 can back
the file up, but only with a registered server. This module reads pages
directly so the data can be browsed without that server.

The on-disk layout follows the InterBase 7 structures documented by the
MIT-licensed DBReader project (serbod/DBReader) and the Firebird ODS notes.
"""

from __future__ import annotations

import mmap
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

PAGE_HEADER = 16
DATA_HEADER = 24  # page header + sequence + relation + count
RECORD_HEADER = 13
FRAGMENT_HEADER = 22
BLOB_HEADER = struct.calcsize("<IIHHBIIHBB")  # 25, packed blh

PAGE_DATA = 5
REC_DELETED = 1
REC_CHAIN = 2
REC_FRAGMENT = 4
REC_INCOMPLETE = 8
REC_BLOB = 16
REC_DAMAGED = 128
SKIP_RECORD = REC_DELETED | REC_CHAIN | REC_FRAGMENT | REC_BLOB | REC_DAMAGED

SYS_PAGES = 0
SYS_FIELDS = 2
SYS_RELATION_FIELDS = 5
SYS_RELATIONS = 6
SYS_FORMATS = 8

DTYPE_TEXT = 1
DTYPE_CSTRING = 2
DTYPE_VARYING = 3
DTYPE_BYTE = 7
DTYPE_SHORT = 8
DTYPE_LONG = 9
DTYPE_QUAD = 10
DTYPE_REAL = 11
DTYPE_DOUBLE = 12
DTYPE_DATE = 14
DTYPE_TIME = 15
DTYPE_TIMESTAMP = 16
DTYPE_BLOB = 17
DTYPE_ARRAY = 18
DTYPE_INT64 = 19

SQL_NAMES = {
    7: "SMALLINT",
    8: "INTEGER",
    10: "FLOAT",
    14: "CHAR",
    16: "BIGINT",
    27: "DOUBLE",
    35: "TIMESTAMP",
    37: "VARCHAR",
    40: "CSTRING",
    261: "BLOB",
}

EPOCH = datetime(1858, 11, 17)
CHARSET = "cp1251"


@dataclass
class Field:
    name: str
    dtype: int = 0
    length: int = 0
    subtype: int = 0
    scale: int = 0
    offset: int = 0
    sql_type: int = 0
    sql_length: int = 0
    sql_subtype: int = 0

    @property
    def type_name(self) -> str:
        base = SQL_NAMES.get(self.sql_type, f"TYPE_{self.sql_type or self.dtype}")
        if self.sql_type in (14, 37) and self.sql_length:
            base = f"{base}({self.sql_length})"
        if self.scale < 0:
            base = f"NUMERIC({base},{ -self.scale})"
        return base


@dataclass
class Table:
    relation_id: int
    name: str
    format_id: int = 0
    fields: list[Field] = field(default_factory=list)
    pages: list[tuple[int, int]] = field(default_factory=list)  # sequence, page
    row_count: int = 0
    rows: list[list] = field(default_factory=list)

    @property
    def is_system(self) -> bool:
        return self.name.startswith(("RDB$", "TMP$", "RelationID="))


def rle_decompress(data: bytes) -> bytes:
    out = bytearray()
    pos = 0
    size = len(data)
    while pos < size:
        length = struct.unpack_from("<b", data, pos)[0]
        pos += 1
        if length > 0:
            out += data[pos : pos + length]
            pos += length
        elif length < 0:
            if pos >= size:
                break
            out += bytes([data[pos]]) * (-length)
            pos += 1
        else:
            break
    return bytes(out)


def decode_text(raw: bytes) -> str:
    raw = raw.split(b"\x00", 1)[0].rstrip(b" ")
    if not raw:
        return ""
    return raw.decode(CHARSET, errors="replace")


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._file = open(self.path, "rb")
        self._mm = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
        self.page_size = 4096
        self.ods_major = 0
        self.ods_minor = 0
        self.implementation = 0
        self.page_count = 0
        self.tables: dict[int, Table] = {}
        self._page_index: dict[tuple[int, int], int] = {}
        self._read_header()
        self._init_system_tables()
        self._scan_pages()
        self._build_schema()

    def close(self) -> None:
        self._mm.close()
        self._file.close()

    def _read_header(self) -> None:
        page = self._mm[:4096]
        page_type = page[0]
        if page_type != 1:
            raise ValueError(f"{self.path} is not an InterBase/Firebird database (page type {page_type})")
        self.page_size = struct.unpack_from("<H", page, 0x10)[0]
        ods_word = struct.unpack_from("<H", page, 0x12)[0]
        self.ods_major = ods_word & 0x0F
        self.ods_minor = struct.unpack_from("<H", page, 0x3E)[0]
        self.implementation = struct.unpack_from("<H", page, 0x3C)[0]
        if self.page_size not in (1024, 2048, 4096, 8192, 16384):
            raise ValueError(f"Unexpected page size {self.page_size}")
        if ods_word & 0x8000:
            raise ValueError("This file is Firebird, not the InterBase database this reader expects")
        if self.ods_major != 11:
            raise ValueError(f"Unsupported ODS {self.ods_major}.{self.ods_minor}; this reader handles InterBase ODS 11")
        self.page_count = len(self._mm) // self.page_size
        self.max_records = (self.page_size - DATA_HEADER) // (4 + RECORD_HEADER)

    def _init_system_tables(self) -> None:
        pages = Table(SYS_PAGES, "RDB$PAGES", fields=[
            Field("PAGE_NUMBER", DTYPE_LONG, 4, offset=0),
            Field("RELATION_ID", DTYPE_SHORT, 2),
            Field("PAGE_SEQUENCE", DTYPE_LONG, 4),
            Field("PAGE_TYPE", DTYPE_SHORT, 2),
        ])
        fields = Table(SYS_FIELDS, "RDB$FIELDS")
        if self.ods_major == 10:
            name_len = 32
            after_names = 116
        else:
            name_len = 68
            after_names = 188
        fields.fields = [
            Field("FIELD_NAME", DTYPE_CSTRING, name_len),
            Field("QUERY_NAME", DTYPE_CSTRING, name_len),
            Field("VALIDATION_BLR", DTYPE_BLOB, 8, 2),
            Field("VALIDATION_SOURCE", DTYPE_TEXT, 8, 1),
            Field("COMPUTED_BLR", DTYPE_BLOB, 8, 2),
            Field("COMPUTED_SOURCE", DTYPE_TEXT, 8, 1),
            Field("DEFAULT_VALUE", DTYPE_BLOB, 8, 2),
            Field("DEFAULT_SOURCE", DTYPE_TEXT, 8, 1),
            Field("FIELD_LENGTH", DTYPE_SHORT, 2),
            Field("FIELD_SCALE", DTYPE_SHORT, 2),
            Field("FIELD_TYPE", DTYPE_SHORT, 2),
            Field("FIELD_SUB_TYPE", DTYPE_SHORT, 2),
            Field("MISSING_VALUE", DTYPE_BLOB, 4, 2),
            Field("MISSING_SOURCE", DTYPE_BLOB, 10, 1),
            Field("DESCRIPTION", DTYPE_BLOB, 10, 1),
            Field("SYSTEM_FLAG", DTYPE_SHORT, 2),
            Field("QUERY_HEADER", DTYPE_TEXT, 14, 1),
            Field("SEGMENT_LENGTH", DTYPE_SHORT, 2),
            Field("EDIT_STRING", DTYPE_VARYING, 126),
            Field("EXTERNAL_LENGTH", DTYPE_SHORT, 2),
            Field("EXTERNAL_SCALE", DTYPE_SHORT, 2),
            Field("EXTERNAL_TYPE", DTYPE_SHORT, 2),
            Field("DIMENSIONS", DTYPE_SHORT, 2),
            Field("NULL_FLAG", DTYPE_SHORT, 2),
            Field("CHARACTER_LENGTH", DTYPE_SHORT, 2),
            Field("COLLATION_ID", DTYPE_SHORT, 2),
            Field("CHARACTER_SET_ID", DTYPE_SHORT, 2),
            Field("FIELD_PRECISION", DTYPE_SHORT, 2),
        ]
        rel_fields = Table(SYS_RELATION_FIELDS, "RDB$RELATION_FIELDS", fields=[
            Field("FIELD_NAME", DTYPE_CSTRING, 67),
            Field("RELATION_NAME", DTYPE_CSTRING, 67),
            Field("FIELD_SOURCE", DTYPE_CSTRING, 67),
            Field("QUERY_NAME", DTYPE_CSTRING, 67),
            Field("BASE_FIELD", DTYPE_CSTRING, 67),
            Field("EDIT_STRING", DTYPE_VARYING, 127),
            Field("FIELD_POSITION", DTYPE_SHORT, 2),
            Field("QUERY_HEADER", DTYPE_TEXT, 10, 1),
            Field("UPDATE_FLAG", DTYPE_SHORT, 2),
            Field("FIELD_ID", DTYPE_SHORT, 2),
            Field("VIEW_CONTEXT", DTYPE_SHORT, 2),
            Field("DESCRIPTION", DTYPE_TEXT, 14, 1),
            Field("DEFAULT_VALUE", DTYPE_BLOB, 4, 2),
            Field("SYSTEM_FLAG", DTYPE_SHORT, 2),
            Field("SECURITY_CLASS", DTYPE_CSTRING, 31),
            Field("COMPLEX_NAME", DTYPE_CSTRING, 31),
            Field("NULL_FLAG", DTYPE_SHORT, 2),
            Field("DEFAULT_SOURCE", DTYPE_TEXT, 14, 1),
            Field("COLLATION_ID", DTYPE_SHORT, 2),
        ])
        relations = Table(SYS_RELATIONS, "RDB$RELATIONS", fields=[
            Field("VIEW_BLR", DTYPE_BLOB, 8, 1),
            Field("VIEW_SOURCE", DTYPE_BLOB, 8, 1),
            Field("DESCRIPTION", DTYPE_BLOB, 8, 1),
            Field("RELATION_ID", DTYPE_SHORT, 2),
            Field("SYSTEM_FLAG", DTYPE_SHORT, 2),
            Field("DBKEY_LENGTH", DTYPE_SHORT, 2),
            Field("FORMAT", DTYPE_SHORT, 2),
            Field("FIELD_ID", DTYPE_SHORT, 2),
            Field("RELATION_NAME", DTYPE_CSTRING, 31),
            Field("SECURITY_CLASS", DTYPE_CSTRING, 31),
            Field("EXTERNAL_FILE", DTYPE_VARYING, 257),
            Field("RUNTIME", DTYPE_BLOB, 8, 5),
            Field("EXTERNAL_DESCRIPTION", DTYPE_BLOB, 8, 8),
            Field("OWNER_NAME", DTYPE_CSTRING, 31),
            Field("DEFAULT_CLASS", DTYPE_CSTRING, 31),
            Field("FLAGS", DTYPE_SHORT, 2),
            Field("RELATION_TYPE", DTYPE_SHORT, 2),
        ])
        formats = Table(SYS_FORMATS, "RDB$FORMATS", fields=[
            Field("RELATION_ID", DTYPE_SHORT, 2),
            Field("FORMAT", DTYPE_SHORT, 2),
            Field("DESCRIPTOR", DTYPE_BLOB, 8, 6),
        ])
        for table in (pages, fields, rel_fields, relations, formats):
            self._place_system_fields(table, force_pos=after_names if table.relation_id == SYS_FIELDS else None)
            self.tables[table.relation_id] = table

    def _place_system_fields(self, table: Table, force_pos: int | None) -> None:
        # Null bitmap is 4 bytes until the table has more than 32 columns.
        pos = ((max(len(table.fields) - 1, 0) // 32) + 1) * 4
        forced = False
        for index, column in enumerate(table.fields):
            if table.relation_id == SYS_FIELDS and index == 8 and force_pos is not None:
                pos = force_pos
                forced = True
            column.offset = pos
            pos += self._field_size(column)
        if table.relation_id == SYS_FIELDS and not forced:
            raise RuntimeError("RDB$FIELDS layout was not anchored")

    @staticmethod
    def _field_size(column: Field) -> int:
        dtype = column.dtype
        length = column.length
        if dtype == DTYPE_TEXT:
            if column.subtype in (0, 3):
                return length
            return 8 if length == 0 else length
        if dtype == DTYPE_CSTRING:
            return length
        if dtype == DTYPE_VARYING:
            return 2 + length
        if dtype == DTYPE_BYTE:
            return 1
        if dtype == DTYPE_SHORT:
            return 2
        if dtype == DTYPE_LONG:
            return 4
        if dtype in (DTYPE_QUAD, DTYPE_DOUBLE, DTYPE_TIMESTAMP, DTYPE_INT64):
            return 8
        if dtype == DTYPE_REAL:
            return 4
        if dtype in (DTYPE_DATE, DTYPE_TIME):
            return 4
        if dtype == DTYPE_BLOB:
            if length:
                return length
            return 4 if column.subtype == 2 else 8
        if dtype == DTYPE_ARRAY:
            return 8
        return length

    def _page(self, number: int) -> memoryview:
        start = number * self.page_size
        return memoryview(self._mm)[start : start + self.page_size]

    def _scan_pages(self) -> None:
        for number in range(1, self.page_count):
            page = self._page(number)
            if page[0] != PAGE_DATA:
                continue
            if page[1] & 1:
                continue  # orphan, not part of the current pointer chain
            relation_id, count = struct.unpack_from("<HH", page, 20)
            sequence = struct.unpack_from("<I", page, 16)[0]
            if count > 2000:
                continue
            table = self.tables.get(relation_id)
            if table is None:
                table = Table(relation_id, f"RelationID={relation_id}")
                self.tables[relation_id] = table
            table.pages.append((sequence, number))
            self._page_index[(relation_id, sequence)] = number
            if relation_id >= 40 or not table.fields:
                table.row_count += self._count_live(page, count)
                continue
            for record in self._live_records(page, count):
                table.rows.append(self._decode(record, table.fields, relation_id))
                table.row_count += 1

    def _count_live(self, page: memoryview, count: int) -> int:
        total = 0
        for offset, length in self._slots(page, count):
            if length < RECORD_HEADER or offset + 12 > self.page_size:
                continue
            flags = struct.unpack_from("<H", page, offset + 10)[0]
            if flags & SKIP_RECORD:
                continue
            total += 1
        return total

    def _slots(self, page: memoryview, count: int):
        for index in range(count):
            at = DATA_HEADER + index * 4
            if at + 4 > self.page_size:
                break
            offset, length = struct.unpack_from("<HH", page, at)
            if length == 0 or offset == 0 or offset + length > self.page_size:
                continue
            yield offset, length

    def _live_records(self, page: memoryview, count: int):
        for offset, length in self._slots(page, count):
            if length < RECORD_HEADER:
                continue
            flags = struct.unpack_from("<H", page, offset + 10)[0]
            if flags & REC_INCOMPLETE:
                if length < FRAGMENT_HEADER:
                    continue
                frag_page, frag_line = struct.unpack_from("<IH", page, offset + 16)
                payload = rle_decompress(bytes(page[offset + FRAGMENT_HEADER : offset + length]))
                payload += self._fragment(frag_page, frag_line)
                if payload:
                    yield payload
                continue
            if flags & SKIP_RECORD or flags != 0:
                continue
            payload = rle_decompress(bytes(page[offset + RECORD_HEADER : offset + length]))
            if payload:
                yield payload

    def _fragment(self, page_number: int, line: int, depth: int = 0) -> bytes:
        if depth > 8 or page_number <= 0 or page_number >= self.page_count:
            return b""
        page = self._page(page_number)
        if page[0] != PAGE_DATA:
            return b""
        count = struct.unpack_from("<H", page, 22)[0]
        slots = list(self._slots(page, count))
        if line >= len(slots):
            # line is the slot index on the page, including empty slots
            raw_slots = []
            for index in range(count):
                at = DATA_HEADER + index * 4
                raw_slots.append(struct.unpack_from("<HH", page, at))
            if line >= len(raw_slots):
                return b""
            offset, length = raw_slots[line]
        else:
            # Prefer the absolute slot index, not the compacted live list.
            at = DATA_HEADER + line * 4
            if at + 4 > self.page_size:
                return b""
            offset, length = struct.unpack_from("<HH", page, at)
        if length < RECORD_HEADER or offset + length > self.page_size:
            return b""
        flags = struct.unpack_from("<H", page, offset + 10)[0]
        if not (flags & REC_FRAGMENT):
            return b""
        return rle_decompress(bytes(page[offset + RECORD_HEADER : offset + length]))

    def _decode(self, data: bytes, fields: list[Field], relation_id: int) -> list:
        values: list = []
        for index, column in enumerate(fields):
            value = self._read_field(data, column)
            if self._is_null(data, index):
                value = None
            values.append(value)
        return values

    def _is_null(self, data: bytes, index: int) -> bool:
        flag_index = index // 8
        if flag_index >= len(data):
            return False
        return (data[flag_index] & (1 << (index % 8))) != 0

    def _read_field(self, data: bytes, column: Field):
        pos = column.offset
        dtype = column.dtype
        if pos < 0 or pos >= len(data):
            return None
        if dtype in (DTYPE_TEXT, DTYPE_CSTRING):
            if column.subtype not in (0, 3) and dtype == DTYPE_TEXT:
                return self._read_blob_pointer(data, pos, column)
            raw = data[pos : pos + column.length]
            return decode_text(raw)
        if dtype == DTYPE_VARYING:
            if pos + 2 > len(data):
                return None
            size = struct.unpack_from("<H", data, pos)[0]
            size = min(size, column.length or size)
            return decode_text(data[pos + 2 : pos + 2 + size])
        if dtype == DTYPE_BYTE:
            return data[pos]
        if dtype == DTYPE_SHORT:
            if pos + 2 > len(data):
                return None
            return self._scale(struct.unpack_from("<h", data, pos)[0], column.scale)
        if dtype == DTYPE_LONG:
            if pos + 4 > len(data):
                return None
            return self._scale(struct.unpack_from("<i", data, pos)[0], column.scale)
        if dtype in (DTYPE_QUAD, DTYPE_INT64):
            if pos + 8 > len(data):
                return None
            value = struct.unpack_from("<q", data, pos)[0]
            if column.subtype == 1 or column.scale < 0:
                return self._scale(value, column.scale if column.scale < 0 else -4 if column.subtype == 1 else 0)
            return value
        if dtype == DTYPE_REAL:
            if pos + 4 > len(data):
                return None
            return struct.unpack_from("<f", data, pos)[0]
        if dtype == DTYPE_DOUBLE:
            if pos + 8 > len(data):
                return None
            return struct.unpack_from("<d", data, pos)[0]
        if dtype == DTYPE_DATE:
            return self._read_date(data, pos, with_time=False)
        if dtype == DTYPE_TIME:
            return self._read_time(data, pos)
        if dtype == DTYPE_TIMESTAMP:
            return self._read_date(data, pos, with_time=True)
        if dtype == DTYPE_BLOB:
            return self._read_blob_pointer(data, pos, column)
        if dtype == DTYPE_ARRAY:
            return None
        return None

    def _scale(self, value: int, scale: int):
        if scale >= 0:
            return value
        return Decimal(value).scaleb(scale)

    def _read_date(self, data: bytes, pos: int, with_time: bool):
        if pos + (8 if with_time else 4) > len(data):
            return None
        days = struct.unpack_from("<i", data, pos)[0]
        part = struct.unpack_from("<i", data, pos + 4)[0] if with_time else 0
        if days == 0 and part == 0:
            return None
        try:
            return EPOCH + timedelta(days=days, microseconds=part * 100)
        except OverflowError:
            return None

    def _read_time(self, data: bytes, pos: int):
        if pos + 4 > len(data):
            return None
        part = struct.unpack_from("<I", data, pos)[0]
        if part == 0:
            return None
        return (EPOCH + timedelta(microseconds=part * 100)).time()

    def _read_blob_pointer(self, data: bytes, pos: int, column: Field):
        if pos + 8 > len(data):
            return None
        _blob_relation, row_id = struct.unpack_from("<iI", data, pos)
        if row_id == 0 and _blob_relation == 0:
            return None
        return ("blob", row_id, column.subtype)

    def _build_schema(self) -> None:
        relations = {self._text(row, 8): row for row in self.tables[SYS_RELATIONS].rows if self._text(row, 8)}
        field_defs = {self._text(row, 0): row for row in self.tables[SYS_FIELDS].rows if self._text(row, 0)}
        by_name: dict[str, Table] = {}
        for row in self.tables[SYS_RELATION_FIELDS].rows:
            relation_name = self._text(row, 1) or self._text(row, 2)
            source_name = self._text(row, 2)
            field_name = self._text(row, 0)
            relation = relations.get(relation_name)
            source = field_defs.get(source_name)
            if relation is None or source is None or not field_name:
                continue
            relation_id = self._int(relation, 3)
            if relation_id is None:
                continue
            table = self.tables.get(relation_id)
            if table is None:
                table = Table(relation_id, relation_name)
                self.tables[relation_id] = table
            table.name = relation_name
            table.format_id = self._int(relation, 6) or 0
            field_id = self._int(row, 9)
            if field_id is None or field_id < 0 or field_id > 10000:
                continue
            while len(table.fields) <= field_id:
                table.fields.append(Field(""))
            table.fields[field_id] = Field(
                name=field_name,
                sql_type=self._int(source, 10) or 0,
                sql_length=self._int(source, 8) or 0,
                scale=self._int(source, 9) or 0,
                sql_subtype=self._int(source, 11) or 0,
            )
            by_name[relation_name] = table

        formats = self.tables[SYS_FORMATS]
        for row in formats.rows:
            relation_id = self._int(row, 0)
            format_id = self._int(row, 1)
            table = self.tables.get(relation_id) if relation_id is not None else None
            if table is None or not table.fields:
                continue
            # Prefer the format version recorded on the relation. Some user
            # tables only have a single descriptor whose number does not match
            # a zero in RDB$RELATIONS.RDB$FORMAT.
            if table.format_id and format_id != table.format_id:
                continue
            pointer = row[2] if len(row) > 2 else None
            if not (isinstance(pointer, tuple) and pointer[0] == "blob"):
                continue
            # The blob record lives in RDB$FORMATS, not in the table it describes.
            blob = self.read_blob(SYS_FORMATS, pointer[1])
            if blob:
                self._apply_format(table, blob)
        for table in self.tables.values():
            table.pages.sort()

    def _apply_format(self, table: Table, blob: bytes) -> None:
        # InterBase ODS 11 stores a short header, then 16-byte field descriptors:
        # pad, dtype, scale, length, subtype, flags, offset.
        record_size = 16
        prefix = self._format_prefix(blob, len([column for column in table.fields if column.name]), record_size)
        for index, column in enumerate(table.fields):
            pos = prefix + index * record_size
            if pos + record_size > len(blob):
                break
            _pad, dtype, scale, length, subtype, _flags, offset = struct.unpack_from("<BBhHHII", blob, pos)
            if dtype <= 0 or dtype > 40:
                continue
            if scale > 0 or scale < -18:
                scale = 0
            column.dtype = dtype
            column.scale = scale
            column.length = length
            column.subtype = subtype
            column.offset = offset

    @staticmethod
    def _format_prefix(blob: bytes, field_count: int, record_size: int) -> int:
        """Return the byte offset where field descriptors start.

        The descriptor blob begins with a version byte and the descriptor
        byte count. Some blobs also carry a 2-byte segment prefix.
        """
        if field_count <= 0:
            return 0
        need = field_count * record_size
        for start in range(0, 8):
            if start + 3 + need > len(blob) + 3:
                continue
            if start + 3 > len(blob):
                break
            version, nbytes = struct.unpack_from("<BH", blob, start)
            if version != 0 or nbytes != need:
                continue
            dtype_at = start + 4
            if dtype_at < len(blob) and 0 < blob[dtype_at] <= 40:
                return start + 3
        for prefix in (3, 5, 4, 2, 0):
            if prefix + 1 < len(blob) and 0 < blob[prefix + 1] <= 40:
                return prefix
        return 3

    def read_blob(self, relation_id: int, row_id: int) -> bytes | None:
        if row_id < 0:
            return None
        sequence, index = divmod(row_id, self.max_records)
        page_number = self._page_index.get((relation_id, sequence))
        if page_number is None:
            return None
        page = self._page(page_number)
        count = struct.unpack_from("<H", page, 22)[0]
        at = DATA_HEADER + index * 4
        if at + 4 > self.page_size:
            return None
        offset, length = struct.unpack_from("<HH", page, at)
        if length < BLOB_HEADER or offset + length > self.page_size:
            return None
        lead, _max_seq, _max_seg, flags, level, _count, _blob_len, subtype, _charset, _unused = struct.unpack_from(
            "<IIHHBIIHBB", page, offset
        )
        if not (flags & REC_BLOB):
            return None
        chunks = bytearray()
        inline = bytes(page[offset + BLOB_HEADER : offset + length])
        if lead:
            chunks += self._read_blob_pages(lead, level)
        elif inline:
            chunks += inline
        if subtype == 1 and len(chunks) >= 2:
            return chunks[2:]
        if subtype == 6:
            return bytes(chunks)
        return bytes(chunks)

    def _read_blob_pages(self, lead: int, level: int, depth: int = 0) -> bytes:
        if depth > 6 or lead <= 0 or lead >= self.page_count:
            return b""
        page = self._page(lead)
        if page[0] != 8:
            return b""
        length = struct.unpack_from("<H", page, 24)[0]
        flags = page[1]
        body = bytes(page[28 : 28 + length]) if 28 + length <= self.page_size else b""
        if flags & 1 or level > 0:
            pages = [struct.unpack_from("<I", body, i)[0] for i in range(0, len(body) - 3, 4)]
            out = bytearray()
            for number in pages:
                if number:
                    out += self._read_blob_pages(number, max(level - 1, 0), depth + 1)
            return bytes(out)
        return body

    def user_tables(self) -> list[Table]:
        tables = [table for table in self.tables.values() if table.name and not table.is_system and not table.name.startswith("RelationID=")]
        return sorted(tables, key=lambda table: table.name)

    def table_by_name(self, name: str) -> Table | None:
        wanted = name.upper()
        for table in self.tables.values():
            if table.name.upper() == wanted:
                return table
        return None

    def rows(self, table: Table, *, offset: int = 0, limit: int = 50, query: str = "") -> tuple[list[list], bool]:
        query = query.strip().casefold()
        skipped = 0
        found: list[list] = []
        scanned = 0
        scan_limit = 200000
        for _sequence, page_number in table.pages:
            page = self._page(page_number)
            if page[0] != PAGE_DATA:
                continue
            count = struct.unpack_from("<H", page, 22)[0]
            for record in self._live_records(page, count):
                scanned += 1
                values = self._present(self._decode(record, table.fields, table.relation_id), table)
                if query and not any(query in cell.casefold() for cell in values if isinstance(cell, str)):
                    if scanned >= scan_limit:
                        return found, True
                    continue
                if skipped < offset:
                    skipped += 1
                    continue
                found.append(values)
                if len(found) > limit:
                    return found[:limit], True
                if scanned >= scan_limit:
                    return found, True
        return found, False

    def _present(self, values: list, table: Table) -> list:
        shown = []
        for column, value in zip(table.fields, values):
            if isinstance(value, tuple) and value and value[0] == "blob":
                blob = self.read_blob(table.relation_id, value[1])
                if blob is None:
                    shown.append(None)
                elif column.subtype == 1 or column.sql_subtype == 1:
                    shown.append(decode_text(blob)[:4000])
                else:
                    shown.append(f"({len(blob)} bytes)")
                continue
            if isinstance(value, datetime):
                shown.append(value.isoformat(sep=" "))
            elif isinstance(value, float):
                shown.append(round(value, 6))
            elif isinstance(value, Decimal):
                shown.append(format(value, "f"))
            else:
                shown.append(value)
        return shown

    @staticmethod
    def _text(row: list, index: int) -> str:
        if index >= len(row) or row[index] is None:
            return ""
        return str(row[index]).strip()

    @staticmethod
    def _int(row: list, index: int) -> int | None:
        if index >= len(row) or row[index] is None:
            return None
        value = row[index]
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.lstrip("-").isdigit():
            return int(value)
        return None


def summary(db: Database) -> str:
    lines = [
        f"file: {db.path}",
        f"ODS: {db.ods_major}.{db.ods_minor} InterBase",
        f"page size: {db.page_size}",
        f"pages: {db.page_count}",
        f"implementation: {db.implementation}",
        "user tables:",
    ]
    for table in db.user_tables():
        columns = ", ".join(column.name for column in table.fields if column.name)
        lines.append(f"  {table.name}  rows≈{table.row_count}  cols={columns}")
    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Inspect an InterBase 7 BUY.GDB copy")
    parser.add_argument("database")
    parser.add_argument("--table")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    db = Database(Path(args.database))
    try:
        if args.table:
            table = db.table_by_name(args.table)
            if table is None:
                raise SystemExit(f"No table {args.table}")
            print(table.name, "rows≈", table.row_count)
            print(", ".join(column.name for column in table.fields if column.name))
            found, _more = db.rows(table, limit=args.limit)
            for row in found:
                print(row)
        else:
            print(summary(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
