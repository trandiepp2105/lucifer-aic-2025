from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Query, Answer

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

class AnswerModelTest(TestCase):
    def setUp(self):
        self.query = Query.objects.create(text="Test query")
        self.answer = Answer.objects.create(
            query=self.query,
            video="test_video.mp4",
            key="test_key"
        )

    def test_answer_creation(self):
        self.assertEqual(self.answer.query, self.query)
        self.assertEqual(self.answer.video, "test_video.mp4")
        self.assertEqual(self.answer.key, "test_key")

    def test_answer_str_method(self):
        expected = f"Answer {self.answer.id} for Query {self.query.id}"
        self.assertEqual(str(self.answer), expected)

    def test_foreign_key_relationship(self):
        # Test that we can access answers from query
        self.assertIn(self.answer, self.query.answers.all())
