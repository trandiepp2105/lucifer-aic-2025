from django.contrib import admin
from django.utils.html import format_html
from .models import Query, Answer, QuerySession, TeamAnswer

@admin.register(QuerySession)
class QuerySessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'queries_count', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['delete_session_and_queries']
    
    fieldsets = (
        ('Session Info', {
            'fields': ('id',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    def queries_count(self, obj):
        count = obj.queries.count()
        if count > 0:
            # Make it a clickable link to filter queries by this session
            url = f'/admin/query/query/?session__id__exact={obj.id}'
            return format_html('<a href="{}">{} queries</a>', url, count)
        return '0 queries'
    queries_count.short_description = 'Number of Queries'
    
    def delete_session_and_queries(self, request, queryset):
        total_queries = 0
        total_sessions = queryset.count()
        
        for session in queryset:
            query_count = session.queries.count()
            total_queries += query_count
            # Delete all queries first (this will also delete associated files)
            session.queries.all().delete()
            # Then delete the session
            session.delete()
        
        self.message_user(
            request,
            f'Successfully deleted {total_sessions} session(s) and {total_queries} associated query(ies).'
        )
    delete_session_and_queries.short_description = "Delete selected sessions and all their queries"

@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    list_display = ['id', 'session_info', 'text_preview', 'time', 'has_image', 'created_at']
    list_filter = ['time', 'created_at', 'session']
    search_fields = ['text', 'ocr', 'speech']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Session', {
            'fields': ('session',)
        }),
        ('Query Content', {
            'fields': ('text', 'ocr', 'speech', 'image', 'background_sound')
        }),
        ('Timestamps', {
            'fields': ('time', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def session_info(self, obj):
        if obj.session:
            return f'Session {obj.session.id}'
        return 'No Session'
    session_info.short_description = 'Session'
    
    def text_preview(self, obj):
        if obj.text:
            return obj.text[:100] + '...' if len(obj.text) > 100 else obj.text
        return 'No text'
    text_preview.short_description = 'Text Preview'
    
    def has_image(self, obj):
        return bool(obj.image)
    has_image.boolean = True
    has_image.short_description = 'Has Image'

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['id', 'video_name', 'frame_index', 'round', 'query_index', 'has_qa', 'created_at']
    list_filter = ['round', 'created_at', 'query_index']
    search_fields = ['video_name', 'qa', 'url']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Frame Information', {
            'fields': ('video_name', 'frame_index', 'url')
        }),
        ('Query Information', {
            'fields': ('round', 'query_index', 'qa')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_qa(self, obj):
        return bool(obj.qa and obj.qa.strip())
    has_qa.boolean = True
    has_qa.short_description = 'Has Q&A Text'

@admin.register(TeamAnswer)
class TeamAnswerAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'video_name', 'frame_index', 'query_index', 
        'round', 'created_at'
    ]
    list_filter = ['round', 'query_index', 'created_at']
    search_fields = ['video_name', 'qa']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Frame Information', {
            'fields': ('video_name', 'frame_index', 'url')
        }),
        ('Query Information', {
            'fields': ('query_index', 'round', 'qa')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request)
    
    actions = ['delete_selected_team_answers']
    
    def delete_selected_team_answers(self, request, queryset):
        """Custom action to delete selected team answers"""
        count = queryset.count()
        queryset.delete()
        self.message_user(
            request,
            f'Successfully deleted {count} team answer(s).'
        )
    delete_selected_team_answers.short_description = "Delete selected team answers"
