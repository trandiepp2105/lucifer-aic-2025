from django.contrib import admin
from .models import SpeechLog


@admin.register(SpeechLog)
class SpeechLogAdmin(admin.ModelAdmin):
    list_display = ['transcript_text_short', 'is_final', 'client_ip', 'timestamp']
    list_filter = ['is_final', 'timestamp']
    search_fields = ['transcript_text', 'client_ip']
    readonly_fields = ['timestamp']
    
    def transcript_text_short(self, obj):
        return obj.transcript_text[:50] + '...' if len(obj.transcript_text) > 50 else obj.transcript_text
    transcript_text_short.short_description = 'Transcript'
