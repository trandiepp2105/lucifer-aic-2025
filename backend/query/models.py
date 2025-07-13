from django.db import models
from django.utils import timezone
import os

def query_image_upload_path(instance, filename):
    """Upload path for query images"""
    return os.path.join('queries', filename)

class QuerySession(models.Model):
    """Model for grouping queries into sessions"""
    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'query_session'
        ordering = ['-created_at']
        verbose_name = 'Query Session'
        verbose_name_plural = 'Query Sessions'

    def __str__(self):
        return f"Session {self.id} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class Query(models.Model):
    """Model for storing user queries"""
    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(
        QuerySession, 
        on_delete=models.CASCADE, 
        related_name='queries',
        null=True,
        blank=True,
        help_text="Session this query belongs to"
    )
    text = models.TextField(null=True, blank=True, help_text="Text content of the query")
    ocr = models.TextField(null=True, blank=True, help_text="OCR extracted text")
    speech = models.TextField(null=True, blank=True, help_text="Speech-to-text content")
    image = models.ImageField(
        upload_to=query_image_upload_path, 
        null=True, 
        blank=True,
        help_text="Uploaded image for the query"
    )
    time = models.DateTimeField(
        default=timezone.now,
        help_text="Timestamp when the query was created"
    )
    background_sound = models.TextField(
        null=True, 
        blank=True, 
        help_text="Background sound information"
    )
    stage = models.PositiveIntegerField(
        default=1,
        help_text="Stage number for query processing (default: 1)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'query'
        ordering = ['-created_at']
        verbose_name = 'Query'
        verbose_name_plural = 'Queries'

    def __str__(self):
        return f"Query {self.id} - {self.text[:50] if self.text else 'No text'}"

    def delete_image_file(self):
        """Delete the associated image file from storage"""
        if self.image:
            try:
                if os.path.isfile(self.image.path):
                    os.remove(self.image.path)
                    print(f"Deleted image file: {self.image.path}")
            except Exception as e:
                print(f"Error deleting image file {self.image.path}: {e}")

    def delete(self, *args, **kwargs):
        """Override delete method to remove image file"""
        self.delete_image_file()
        super().delete(*args, **kwargs)
