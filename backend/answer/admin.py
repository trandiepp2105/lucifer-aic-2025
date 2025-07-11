from django.contrib import admin
from .models import Answer, TeamAnswer

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'video_name', 'frame_index', 'query_index', 'round', 'created_at')
    list_filter = ('round', 'created_at', 'query_index')
    search_fields = ('video_name', 'qa', 'url')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('video_name', 'frame_index', 'url', 'query_index', 'round')
        }),
        ('Content', {
            'fields': ('qa',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(TeamAnswer)
class TeamAnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'video_name', 'frame_index', 'query_index', 'round', 'created_at')
    list_filter = ('round', 'created_at', 'query_index')
    search_fields = ('video_name', 'qa', 'url')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('video_name', 'frame_index', 'url', 'query_index', 'round')
        }),
        ('Content', {
            'fields': ('qa',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
