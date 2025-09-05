from django.db import models
from django.utils import timezone


class SpeechLog(models.Model):
    """
    Simple model to log speech recognition activity
    """
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    transcript_text = models.TextField()
    is_final = models.BooleanField(default=False)
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"Speech Log: {self.transcript_text[:50]}"
