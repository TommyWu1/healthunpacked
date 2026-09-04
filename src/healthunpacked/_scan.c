/*
 * A scanner for Apple Health's export.xml.
 *
 * Deliberately not an XML parser. A health export is a flat list of
 * <Record .../> elements: no nesting worth speaking of, no namespaces,
 * no mixed content. A real parser pays for all of that. This walks the
 * bytes looking for one string, "<Record ", and pulls the attributes it
 * wants out of whatever follows.
 *
 * The whole file is read through one fixed buffer, so memory does not
 * grow with the input. That is the point of the exercise.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <stdio.h>
#include <string.h>

/* How much we read at a time. */
#define WINDOW 	   (1u << 20)   /* 1 MiB */

/* A single <Record> longer than this means the input is not what we think
 * it is. Bounding it stops a malformed file from growing the buffer forever. */
#define MAX_RECORD (1u << 16)   /* 64 KiB */

/* An export uses on the order of 100 distinct type identifiers. A fixed
 * table avoids any allocation while scanning, and 256 leaves plenty of room. */
#define MAX_TYPES  256
#define MAX_TYPE_LEN 128

static const char OPEN_TAG[] = "<Record ";
#define OPEN_TAG_LEN (sizeof(OPEN_TAG) - 1)


/* ---------------------------------------------------------------- counting */
/*
 * Types are counted here, in C, rather than in a Python dict. Touching the
 * Python heap once per record would hand back most of the speed: the cost of
 * a C extension is crossing the boundary, not the C. So we cross once, at
 * the end, when we build the dict from this table.
 *
 * A linear scan of ~100 short strings is faster in practice than hashing them.
 */

typedef struct {
    char name[MAX_TYPE_LEN];
    size_t len;
    unsigned long long count;
} type_count;

typedef struct {
    type_count items[MAX_TYPES];
    size_t used;
    int overflowed;
} type_table;

static void count_type(type_table *table, const char *name, size_t len)
{
    if (len >= MAX_TYPE_LEN) {
        return;
    }

    for (size_t i = 0; i < table->used; i++) {
        if (table->items[i].len == len &&
            memcmp(table->items[i].name, name, len) == 0) {
            table->items[i].count++;
            return;
        }
    }

    if (table->used == MAX_TYPES) {
        table->overflowed = 1;
        return;
    }

    type_count *slot = &table->items[table->used++];
    memcpy(slot->name, name, len);
    slot->len = len;
    slot->count = 1;
}


/* ----------------------------------------------------------------- finding */

/* Plain substring search. No strstr because the buffer is not NUL-terminated. */
static const char *find(const char *haystack, size_t haystack_len,
                        const char *needle, size_t needle_len)
{
    if (haystack_len < needle_len) {
        return NULL;
    }

    const char *last = haystack + (haystack_len - needle_len);
    for (const char *p = haystack; p <= last; p++) {
        if (*p == *needle && memcmp(p, needle, needle_len) == 0) {
            return p;
        }
    }
    return NULL;
}

/* Find name="..." inside one record and point at the value. */
static int read_attribute(const char *record, size_t record_len,
                          const char *name, size_t name_len,
                          const char **value, size_t *value_len)
{
    char pattern[32];
    if (name_len + 2 > sizeof(pattern)) {
        return 0;
    }
    memcpy(pattern, name, name_len);
    pattern[name_len] = '=';
    pattern[name_len + 1] = '"';

    const char *found = find(record, record_len, pattern, name_len + 2);
    if (found == NULL) {
        return 0;
    }

    const char *start = found + name_len + 2;
    size_t left = record_len - (size_t)(start - record);
    const char *closing_quote = memchr(start, '"', left);
    if (closing_quote == NULL) {
        return 0;
    }

    *value = start;
    *value_len = (size_t)(closing_quote - start);
    return 1;
}


/* -------------------------------------------------------------------- scan */

PyDoc_STRVAR(scan_doc,
"scan(path)\n"
"\n"
"Read an Apple Health export and count records by type.\n"
"Returns (total_records, {type_identifier: count}).");

static PyObject *scan(PyObject *module, PyObject *args)
{
    const char *path;
    if (!PyArg_ParseTuple(args, "s:scan", &path)) {
        return NULL;
    }

    FILE *file = fopen(path, "rb");
    if (file == NULL) {
        PyErr_SetFromErrnoWithFilename(PyExc_OSError, path);
        return NULL;
    }

    /* One buffer for the whole run. The extra MAX_RECORD is headroom for a
     * record left over from the previous window (see "leftover" below). */
    static char buffer[WINDOW + MAX_RECORD];

    type_table table = {0};
    unsigned long long total = 0;
    size_t leftover = 0;      /* bytes carried from the last window */
    int record_too_long = 0;

    /* Nothing below touches Python objects, so let other threads run. */
    Py_BEGIN_ALLOW_THREADS

    for (;;) {
        size_t bytes_read = fread(buffer + leftover, 1, WINDOW, file);
        if (bytes_read == 0) {
            break;
        }

        size_t filled = leftover + bytes_read;
        size_t at = 0;

        for (;;) {
            const char *open = find(buffer + at, filled - at,
                                    OPEN_TAG, OPEN_TAG_LEN);
            if (open == NULL) {
                /* No more records here. Keep just enough bytes that a
                 * "<Record " split across the boundary is still found. */
                size_t keep = OPEN_TAG_LEN - 1;
                at = (filled > keep) ? filled - keep : 0;
                break;
            }

            size_t record_at = (size_t)(open - buffer);
            const char *close = find(buffer + record_at, filled - record_at,
                                     "/>", 2);
            if (close == NULL) {
                /* The record runs past the end of what we have read.
                 * Rewind to its start and pick it up next time around. */
                at = record_at;
                break;
            }

            size_t record_len = (size_t)(close - open) + 2;

            const char *type;
            size_t type_len;
            if (read_attribute(open, record_len, "type", 4, &type, &type_len)) {
                count_type(&table, type, type_len);
            }
            total++;

            at = record_at + record_len;
        }

        leftover = filled - at;
        if (leftover > MAX_RECORD) {
            record_too_long = 1;
            break;
        }
        memmove(buffer, buffer + at, leftover);
    }

    Py_END_ALLOW_THREADS

    fclose(file);

    if (record_too_long) {
        PyErr_SetString(PyExc_ValueError,
                        "found a record over 64 KiB; this does not look like "
                        "a health export");
        return NULL;
    }
    if (table.overflowed) {
        PyErr_SetString(PyExc_ValueError,
                        "more than 256 distinct record types; this does not "
                        "look like a health export");
        return NULL;
    }

    /* The one and only crossing into Python. */
    PyObject *counts = PyDict_New();
    if (counts == NULL) {
        return NULL;
    }

    for (size_t i = 0; i < table.used; i++) {
        PyObject *key = PyUnicode_FromStringAndSize(table.items[i].name,
                                                    (Py_ssize_t)table.items[i].len);
        PyObject *value = PyLong_FromUnsignedLongLong(table.items[i].count);

        if (key == NULL || value == NULL || PyDict_SetItem(counts, key, value) < 0) {
            Py_XDECREF(key);
            Py_XDECREF(value);
            Py_DECREF(counts);
            return NULL;
        }
        Py_DECREF(key);
        Py_DECREF(value);
    }

    return Py_BuildValue("KN", total, counts);
}



/* ----------------------------------------------------------------- series */
/*
 * Same window-and-carry walk as scan(), but instead of tallying every
 * record it pulls (startDate, value) out of the ones matching one
 * requested type and appends them to two Python lists.
 *
 * scan() never touches a Python object inside its read loop, which is
 * what lets it release the GIL for the whole thing. This can't do that:
 * building the timestamp string and the float, and appending them,
 * are all Python C-API calls that need the GIL held. The GIL is only
 * free time here anyway, since the cost of a big export is scanning
 * bytes, not the handful of appends for one series.
 */

PyDoc_STRVAR(read_series_doc,
"read_series(path, record_type)\n"
"\n"
"Return (timestamps, values) for every record of one type.\n"
"Only meaningful for numeric records - heart rate, step count, and so on.");

static PyObject *read_series(PyObject *module, PyObject *args)
{
    const char *path;
    const char *want_type;
    Py_ssize_t want_type_len;
    if (!PyArg_ParseTuple(args, "ss#:read_series",
                          &path, &want_type, &want_type_len)) {
        return NULL;
    }

    FILE *file = fopen(path, "rb");
    if (file == NULL) {
        PyErr_SetFromErrnoWithFilename(PyExc_OSError, path);
        return NULL;
    }

    PyObject *timestamps = PyList_New(0);
    PyObject *values = PyList_New(0);
    if (timestamps == NULL || values == NULL) {
        Py_XDECREF(timestamps);
        Py_XDECREF(values);
        fclose(file);
        return NULL;
    }

    static char buffer[WINDOW + MAX_RECORD];
    size_t leftover = 0;
    int record_too_long = 0;

    for (;;) {
        size_t bytes_read = fread(buffer + leftover, 1, WINDOW, file);
        if (bytes_read == 0) {
            break;
        }

        size_t filled = leftover + bytes_read;
        size_t at = 0;

        for (;;) {
            const char *open = find(buffer + at, filled - at,
                                    OPEN_TAG, OPEN_TAG_LEN);
            if (open == NULL) {
                size_t keep = OPEN_TAG_LEN - 1;
                at = (filled > keep) ? filled - keep : 0;
                break;
            }

            size_t record_at = (size_t)(open - buffer);
            const char *close = find(buffer + record_at, filled - record_at,
                                     "/>", 2);
            if (close == NULL) {
                at = record_at;
                break;
            }

            size_t record_len = (size_t)(close - open) + 2;

            const char *type_val;
            size_t type_len;
            int is_wanted = read_attribute(open, record_len, "type", 4,
                                           &type_val, &type_len)
                          && type_len == (size_t)want_type_len
                          && memcmp(type_val, want_type, type_len) == 0;

            if (is_wanted) {
                const char *date_val, *value_val;
                size_t date_len, value_len;
                int have_date = read_attribute(open, record_len,
                                               "startDate", 9,
                                               &date_val, &date_len);
                int have_value = read_attribute(open, record_len,
                                                "value", 5,
                                                &value_val, &value_len);

                if (have_date && have_value && value_len < 64) {
                    char number[64];
                    memcpy(number, value_val, value_len);
                    number[value_len] = '\0';

                    char *end;
                    double parsed = strtod(number, &end);

                    if (end != number) {
                        PyObject *ts = PyUnicode_FromStringAndSize(
                            date_val, (Py_ssize_t)date_len);
                        PyObject *val = PyFloat_FromDouble(parsed);

                        if (ts == NULL || val == NULL ||
                            PyList_Append(timestamps, ts) < 0 ||
                            PyList_Append(values, val) < 0) {
                            Py_XDECREF(ts);
                            Py_XDECREF(val);
                            Py_DECREF(timestamps);
                            Py_DECREF(values);
                            fclose(file);
                            return NULL;
                        }
                        Py_DECREF(ts);
                        Py_DECREF(val);
                    }
                }
            }

            at = record_at + record_len;
        }

        leftover = filled - at;
        if (leftover > MAX_RECORD) {
            record_too_long = 1;
            break;
        }
        memmove(buffer, buffer + at, leftover);
    }

    fclose(file);

    if (record_too_long) {
        Py_DECREF(timestamps);
        Py_DECREF(values);
        PyErr_SetString(PyExc_ValueError,
                        "found a record over 64 KiB; this does not look like "
                        "a health export");
        return NULL;
    }

    return Py_BuildValue("NN", timestamps, values);
}


static PyMethodDef methods[] = {
    {"scan", scan, METH_VARARGS, scan_doc},
    {"read_series", read_series, METH_VARARGS, read_series_doc},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT,
    "healthunpacked._scan",
    "Scanner for Apple Health exports.",
    -1,
    methods,
};

PyMODINIT_FUNC PyInit__scan(void)
{
    return PyModule_Create(&module_def);
}
