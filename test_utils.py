# cd c:\Docs\Code\lawn
# kr *.py -r -c "python manage.py test test_utils"

import logging
import os

from   django.test import TestCase
from   utils import LoggingFilterContext, TemporaryFileContext


class TestLoggingFilter(TestCase):

    def test_filtering(self):
        calls = list()
        def test_fn(record):
            calls.append( record )

        # Outter filters are checked first.
        with LoggingFilterContext( lambda record: False ):
            with LoggingFilterContext( test_fn ):
                logging.error('pass')
        with LoggingFilterContext( lambda record: True ):
            with LoggingFilterContext( test_fn ):
                logging.error('fail')

        self.assertEquals( ['fail'], [x.msg for x in calls])

    def test_filtering_annotate(self):
        calls = list()
        @LoggingFilterContext.annotate(lambda rec: rec.msg=='pass')
        def test_fn(record):
            calls.append( record )

        with test_fn.logging_filter:
            with LoggingFilterContext( test_fn ):
                logging.warn('pass')
        with test_fn.logging_filter:
            with LoggingFilterContext( test_fn ):
                logging.warn('fail')

        self.assertEquals( ['pass'], [x.msg for x in calls])

    def test_filtering_annotate_regex(self):
        calls = list()
        @LoggingFilterContext.annotate_regex('.*pass$')
        def test_fn(record):
            calls.append( record )

        with test_fn.logging_filter:
            with LoggingFilterContext( test_fn ):
                logging.warn('pass')
        with test_fn.logging_filter:
            with LoggingFilterContext( test_fn ):
                logging.warn('fail')

        self.assertEquals( ['pass'], [x.msg for x in calls])

    def test_filtering_annotate_not_regex(self):
        calls = list()
        @LoggingFilterContext.annotate_not_regex('.*fail$')
        def test_fn(record):
            calls.append( record )

        with test_fn.logging_filter:
            with LoggingFilterContext( test_fn ):
                logging.warn('pass')
        with test_fn.logging_filter:
            with LoggingFilterContext( test_fn ):
                logging.warn('fail')

        self.assertEquals( ['pass'], [x.msg for x in calls])






class TestTemporaryFileContext(TestCase):

    def test_file_is_removed(self):
        contents = 'asd'
        with TemporaryFileContext(contents) as tempfile:
            fname = tempfile.fileName()
            self.assertTrue( os.access(fname, os.R_OK) )
            self.assertEquals( contents, open(fname).read() )
        self.assertFalse( os.access(fname, os.R_OK) )


