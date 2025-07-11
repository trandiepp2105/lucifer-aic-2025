from django.db import models

class Answer(models.Model):
    """Model for storing answers to queries"""
    
    # Round choices
    ROUND_CHOICES = [
        ('prelims', 'Prelims'),
        ('final', 'Final'),
    ]
    
    id = models.AutoField(primary_key=True)
    video_name = models.CharField(
        max_length=500,
        default='',
        help_text="Name of the video"
    )
    frame_index = models.IntegerField(
        default=0,
        help_text="Frame index in the video"
    )
    url = models.TextField(
        default='',
        help_text="URL of the frame image"
    )
    qa = models.TextField(
        null=True, 
        blank=True, 
        help_text="Question and answer text"
    )
    query_index = models.IntegerField(
        default=0,
        help_text="Query index number (default: 0)"
    )
    round = models.CharField(
        max_length=10,
        choices=ROUND_CHOICES,
        default='prelims',
        help_text="Round type: prelims or final"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'answer'
        ordering = ['-created_at']
        verbose_name = 'Answer'
        verbose_name_plural = 'Answers'

    def __str__(self):
        return f"Answer {self.id} - {self.video_name} Frame {self.frame_index} ({self.round})"

class TeamAnswer(models.Model):
    """Model for storing temporary team answers"""
    
    # Round choices
    ROUND_CHOICES = [
        ('prelims', 'Prelims'),
        ('final', 'Final'),
    ]
    
    id = models.AutoField(primary_key=True)
    video_name = models.CharField(
        max_length=500,
        help_text="Name of the video"
    )
    frame_index = models.IntegerField(
        help_text="Frame index in the video"
    )
    url = models.TextField(
        help_text="URL of the frame image"
    )
    qa = models.TextField(
        null=True, 
        blank=True, 
        help_text="Question and answer text"
    )
    query_index = models.IntegerField(
        default=0,
        help_text="Query index number (default: 0)"
    )
    round = models.CharField(
        max_length=10,
        choices=ROUND_CHOICES,
        default='prelims',
        help_text="Round type: prelims or final"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'team_answer'
        ordering = ['-created_at']
        verbose_name = 'Team Answer'
        verbose_name_plural = 'Team Answers'
        # Unique constraint for video_name, frame_index, query_index combination
        unique_together = ['video_name', 'frame_index', 'query_index']

    def __str__(self):
        return f"TeamAnswer {self.id} - {self.video_name} Frame {self.frame_index} Query {self.query_index} ({self.round})"
