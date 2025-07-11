from django.test import TestCase
from django.core.exceptions import ValidationError
from .models import Answer, TeamAnswer

class AnswerModelTest(TestCase):
    def setUp(self):
        self.answer = Answer.objects.create(
            video_name="test_video.mp4",
            frame_index=100,
            url="http://example.com/frame.jpg",
            qa="What is this? This is a test frame.",
            query_index=1,
            round="prelims"
        )

    def test_answer_creation(self):
        self.assertEqual(self.answer.video_name, "test_video.mp4")
        self.assertEqual(self.answer.frame_index, 100)
        self.assertEqual(self.answer.url, "http://example.com/frame.jpg")
        self.assertEqual(self.answer.qa, "What is this? This is a test frame.")
        self.assertEqual(self.answer.query_index, 1)
        self.assertEqual(self.answer.round, "prelims")

    def test_answer_str_method(self):
        expected = f"Answer {self.answer.id} - test_video.mp4 Frame 100 (prelims)"
        self.assertEqual(str(self.answer), expected)

    def test_answer_default_values(self):
        answer = Answer.objects.create(
            video_name="test2.mp4",
            frame_index=50,
            url="http://example.com/frame2.jpg"
        )
        self.assertEqual(answer.query_index, 0)
        self.assertEqual(answer.round, "prelims")

class TeamAnswerModelTest(TestCase):
    def setUp(self):
        self.team_answer = TeamAnswer.objects.create(
            video_name="team_video.mp4",
            frame_index=200,
            url="http://example.com/team_frame.jpg",
            qa="Team question and answer",
            query_index=2,
            round="final"
        )

    def test_team_answer_creation(self):
        self.assertEqual(self.team_answer.video_name, "team_video.mp4")
        self.assertEqual(self.team_answer.frame_index, 200)
        self.assertEqual(self.team_answer.url, "http://example.com/team_frame.jpg")
        self.assertEqual(self.team_answer.qa, "Team question and answer")
        self.assertEqual(self.team_answer.query_index, 2)
        self.assertEqual(self.team_answer.round, "final")

    def test_team_answer_str_method(self):
        expected = f"TeamAnswer {self.team_answer.id} - team_video.mp4 Frame 200 Query 2 (final)"
        self.assertEqual(str(self.team_answer), expected)

    def test_team_answer_unique_constraint(self):
        # Test that creating another team answer with same video_name, frame_index, query_index fails
        with self.assertRaises(Exception):  # Will raise IntegrityError due to unique_together
            TeamAnswer.objects.create(
                video_name="team_video.mp4",
                frame_index=200,
                url="http://example.com/different_frame.jpg",
                query_index=2
            )

    def test_team_answer_default_values(self):
        team_answer = TeamAnswer.objects.create(
            video_name="test_team.mp4",
            frame_index=75,
            url="http://example.com/test_team_frame.jpg"
        )
        self.assertEqual(team_answer.query_index, 0)
        self.assertEqual(team_answer.round, "prelims")
