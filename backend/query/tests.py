from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Query

class QueryModelTest(TestCase):
    def setUp(self):
        self.query = Query.objects.create(
            text="Test query",
            ocr="Test OCR text",
            speech="Test speech text"
        )

    def test_query_creation(self):
        self.assertEqual(self.query.text, "Test query")
        self.assertEqual(self.query.ocr, "Test OCR text")
        self.assertEqual(self.query.speech, "Test speech text")
        self.assertIsNotNone(self.query.time)

    def test_query_str_method(self):
        expected = f"Query {self.query.id} - Test query"
        self.assertEqual(str(self.query), expected)
