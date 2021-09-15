#!/usr/bin/env python
#
# See http://www.python.org/dev/peps/pep-0249/
#
# Many docstrings in this file are based on the PEP, which is in the public domain.

# Built as per Python DB API Specification - PEP 249
# Responsible for connection to Database and providing database cursor for query execution
# Connector is imported and used by Dialect to get connection

import itertools
import json
from collections import namedtuple, OrderedDict

from firebolt_db.firebolt_api_service import FireboltApiService
from firebolt_db import exceptions


class Error(Exception):
    """Exception that is the base class of all other error exceptions.
    You can use this to catch all errors with one single except statement.
    """
    pass


class Type(object):
    STRING = 1
    NUMBER = 2
    BOOLEAN = 3


def connect(*args, **kwargs):
    """
    Constructor for creating a connection to the database.

        >>> connection = connect('localhost',8123,'aapurva@sigmoidanalytics.com', 'Apurva111', 'Sigmoid_Alchemy')
        >>> cursor = connection.cursor()
        >>> response = cursor.execute('select * from <table_name>').fetchall()

    """
    return Connection(*args, **kwargs)


def check_closed(f):
    """Decorator that checks if connection/cursor is closed."""

    def g(self, *args, **kwargs):
        if self.closed:
            raise exceptions.Error(
                "{klass} already closed".format(klass=self.__class__.__name__)
            )
        return f(self, *args, **kwargs)

    return g


def check_result(f):
    """Decorator that checks if the cursor has results from `execute`."""

    def g(self, *args, **kwargs):
        if self._results is None:
            raise exceptions.Error("Called before `execute`")
        return f(self, *args, **kwargs)

    return g


def get_description_from_row(row):
    """
    Return description from a single row.

    We only return the name, type (inferred from the data) and if the values
    can be NULL. String columns in Firebolt are NULLable. Numeric columns are NOT
    NULL.
    """
    return [
        (
            name,  # name
            get_type(value),  # type_code
            None,  # [display_size]
            None,  # [internal_size]
            None,  # [precision]
            None,  # [scale]
            get_type(value) == Type.STRING,  # [null_ok]
        )
        for name, value in row.items()
    ]


def get_type(value):
    """
    Infer type from value.

    Note that bool is a subclass of int so order of statements matter.
    """

    if isinstance(value, str) or value is None:
        return Type.STRING
    elif isinstance(value, bool):
        return Type.BOOLEAN
    elif isinstance(value, (int, float)):
        return Type.NUMBER

    raise exceptions.Error("Value of unknown type: {value}".format(value=value))


class Connection(object):
    """Connection to a Firebolt database."""

    def __init__(self,
                 host,
                 port,
                 username,
                 password,
                 db_name,
                 # scheme="http",
                 context=None,
                 header=False,
                 ssl_verify_cert=False,
                 ssl_client_cert=None,
                 proxies=None,
                 ):
        self._host = host
        self._post = port
        self._username = username
        self._password = password
        self._db_name = db_name
        connection_details = FireboltApiService.get_connection(username, password, db_name)

        self.access_token = connection_details[0]
        self.engine_url = connection_details[1]
        self.refresh_token = connection_details[2]
        self.cursors = []
        self.closed = False

        self.ssl_verify_cert = ssl_verify_cert
        self.ssl_client_cert = ssl_client_cert
        self.proxies = proxies
        self.context = context or {}
        self.header = header


    @check_closed
    def close(self):
        """Close the connection now."""
        self.closed = True
        for cursor in self.cursors:
            try:
                cursor.close()
            except exceptions.Error:
                pass  # already closed

    @check_closed
    def commit(self):
        """
        Commit any pending transaction to the database.

        Not supported.
        """
        pass

    @check_closed
    def cursor(self):
        """Return a new Cursor Object using the connection."""
        cursor = Cursor(
            self._db_name,
            self.access_token,
            self.engine_url,
            self.refresh_token,
            # self.url,
            self._username,
            self._password,
            self.context,
            self.header,
            self.ssl_verify_cert,
            self.ssl_client_cert,
            self.proxies,
        )

        self.cursors.append(cursor)

        return cursor

    # @check_closed
    # def execute(self, operation, parameters=None):
    #     print("***Inside connection.execute()***")
    #     cursor = self.cursor()
    #     cursor.execute(operation, parameters)
    #     print("***Cursor type***")
    #     # print(cursor._results)
    #     print(type(cursor))
    #     print("***Exiting connection.execute()***")
    #     return cursor

    def __enter__(self):
        return self.cursor()

    def __exit__(self, *exc):
        self.close()


class Cursor(object):
    """Connection cursor."""

    def __init__(
            self,
            db_name,
            access_token,
            engine_url,
            refresh_token,
            # url,
            user=None,
            password=None,
            context=None,
            header=False,
            ssl_verify_cert=True,
            proxies=None,
            ssl_client_cert=None,
    ):
        # self.url = url
        self.context = context or {}
        self.header = header
        self.user = user
        self.password = password
        self.ssl_verify_cert = ssl_verify_cert
        self.ssl_client_cert = ssl_client_cert
        self.proxies = proxies
        self.db_name = db_name
        self.access_token = access_token
        self.engine_url = engine_url
        self.refresh_token = refresh_token

        # This read/write attribute specifies the number of rows to fetch at a
        # time with .fetchmany(). It defaults to 1 meaning to fetch a single
        # row at a time.
        self.arraysize = 1

        self.closed = False

        # this is updated only after a query
        self.description = None

        # this is set to an iterator after a successfull query
        self._results = None

    # def __init__(self, db_name, access_token, engine_url, refresh_token):
    #
    #     self._db_name = db_name
    #     self._access_token = access_token
    #     self._engine_url = engine_url
    #     self._refresh_token = refresh_token
    #     self.closed = False
    #
    #     # This read/write attribute specifies the number of rows to fetch at a
    #     # time with .fetchmany(). It defaults to 1 meaning to fetch a single
    #     # row at a time.
    #     self.arraysize = 1
    #
    #     self.closed = False
    #
    #     # this is updated only after a query
    #     self.description = None
    #
    #     # this is set to an iterator after a successfull query
    #     self._results = None
    #     self.header = False

    @property
    @check_result
    @check_closed
    def rowcount(self):
        # consume the iterator
        results = list(self._results)
        n = len(results)
        self._results = iter(results)
        return n

    @check_closed
    def close(self):
        """Close the cursor."""
        self.closed = True

    @check_closed
    def execute(self, operation, parameters=None):
        # def execute(self, operation, parameters=None):
        print("***Inside cursor inside execute()***")
        query = apply_parameters(operation, parameters)
        results = self._stream_query(query)

        """
        `_stream_query` returns a generator that produces the rows; we need to
        consume the first row so that `description` is properly set, so let's
        consume it and insert it back if it is not the header.
        """
        try:
            # first_row = next(results)
            # self._results = (
            #     results if self.header else itertools.chain([first_row], results)
            # )
            self._results = itertools.chain(results)
            print("Type of results in cursor execute")
            print(type(self._results))
        except StopIteration:
            self._results = iter([])
        print("***Exiting cursor execute()***")
        return self

    @check_closed
    def executemany(self, operation, seq_of_parameters=None):
        raise exceptions.NotSupportedError(
            "`executemany` is not supported, use `execute` instead"
        )

    @check_result
    @check_closed
    def fetchone(self):
        """
        Fetch the next row of a query result set, returning a single sequence,
        or `None` when no more data is available.
        """
        try:
            res = self.next()
            print("***Inside fetchone***")
            print(res)
            print(type(res))
            print("***Exiting fetchone***")
            return res
        except StopIteration:
            return None

    @check_result
    @check_closed
    def fetchmany(self, size=None):
        """
        Fetch the next set of rows of a query result, returning a sequence of
        sequences (e.g. a list of tuples). An empty sequence is returned when
        no more rows are available.
        """
        size = size or self.arraysize
        return list(itertools.islice(self._results, size))

    @check_result
    @check_closed
    def fetchall(self):
        """
        Fetch all (remaining) rows of a query result, returning them as a
        sequence of sequences (e.g. a list of tuples). Note that the cursor's
        arraysize attribute can affect the performance of this operation.
        """
        return list(self._results)

    @check_closed
    def setinputsizes(self, sizes):
        # not supported
        pass

    @check_closed
    def setoutputsizes(self, sizes):
        # not supported
        pass

    @check_closed
    def __iter__(self):
        return self

    @check_closed
    def __next__(self):
        return next(self._results)

    next = __next__

    def _stream_query(self, query):
        """
        Stream rows from a query.

        This method will yield rows as the data is returned in chunks from the
        server.
        """
        self.description = None

        r = FireboltApiService.run_query(self.access_token,
                                         self.refresh_token,
                                         self.engine_url,
                                         self.db_name,
                                         query)

        # Setting `chunk_size` to `None` makes it use the server size
        chunks = r.iter_content(chunk_size=None, decode_unicode=True)
        Row = None
        for row in rows_from_chunks(chunks):
            # TODO Check if row description has to be set
            # # update description
            # if self.description is None:
            #     self.description = (
            #         list(row.items()) if self.header else get_description_from_row(row)
            #     )

            # return row in namedtuple
            if Row is None:
                Row = namedtuple("Row", row.keys(), rename=True)
            yield Row(*row.values())


def rows_from_chunks(chunks):
    """
    A generator that yields rows from JSON chunks.

    Firebolt will return the data in chunks, but they are not aligned with the
    JSON objects. This function will parse all complete rows inside each chunk,
    yielding them as soon as possible.
    """
    body = ""
    # count = 1
    squareBrackets = 0
    dataStartpos = 0
    dataEndPos = 0
    inString = False
    for chunk in chunks:
        # print("Chunk:", count)  # Code for testing response being processed in
        # count = count + 1

        if chunk:
            body = "".join((body, chunk))
        for i, char in enumerate(body):
            if char == '"':
                if not inString:
                    inString = True
                else:
                    inString = False

            if not inString:
                if char == '[':
                    squareBrackets += 1
                    if squareBrackets == 2:
                        dataStartpos = i + 1
                if char == ']' and squareBrackets == 2:
                    dataEndPos = i
                    break

        rows = body[dataStartpos:dataEndPos].lstrip().rstrip()
        # print(rows)

        for row in json.loads(
                "[{rows}]".format(rows=rows), object_pairs_hook=OrderedDict
        ):
            yield row


def apply_parameters(operation, parameters):
    if not parameters:
        return operation

    escaped_parameters = {key: escape(value) for key, value in parameters.items()}
    return operation % escaped_parameters


def escape(value):
    """
    Escape the parameter value.

    Note that bool is a subclass of int so order of statements matter.
    """

    if value == "*":
        return value
    elif isinstance(value, str):
        return "'{}'".format(value.replace("'", "''"))
    elif isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    elif isinstance(value, (int, float)):
        return value
    elif isinstance(value, (list, tuple)):
        return ", ".join(escape(element) for element in value)
