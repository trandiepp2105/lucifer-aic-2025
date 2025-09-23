from django.contrib import admin
from .models import Answer, TeamAnswer, TeamTRAKEAnswer, DresSession

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

@admin.register(TeamTRAKEAnswer)
class TeamTRAKEAnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'video_name', 'frame_index', 'query_index', 'group', 'created_at')
    list_filter = ('group', 'created_at', 'query_index')
    search_fields = ('video_name', 'url')
    ordering = ('-created_at', 'group', 'frame_index')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('video_name', 'frame_index', 'url', 'query_index')
        }),
        ('Group Information', {
            'fields': ('group',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Add custom actions
    actions = ['delete_selected_groups']
    
    def delete_selected_groups(self, request, queryset):
        """Delete all items in the same groups as selected items"""
        groups = queryset.values_list('group', flat=True).distinct()
        total_deleted = 0
        for group in groups:
            count = TeamTRAKEAnswer.objects.filter(group=group).count()
            TeamTRAKEAnswer.objects.filter(group=group).delete()
            total_deleted += count
        
        self.message_user(request, f'Successfully deleted {total_deleted} TRAKE answers from {len(groups)} group(s).')
    
    delete_selected_groups.short_description = "Delete entire groups of selected items"
    
    # Custom list view methods
    def get_queryset(self, request):
        """Optimize queryset for admin list view"""
        return super().get_queryset(request).select_related()


@admin.register(DresSession)
class DresSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'role', 'session_id_short', 'evaluation_id', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('username', 'session_id', 'evaluation_id')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at')
    
    fieldsets = (
        ('Session Information', {
            'fields': ('username', 'role', 'session_id', 'evaluation_id')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def session_id_short(self, obj):
        """Display shortened session ID for better readability"""
        return f"{obj.session_id[:12]}..." if len(obj.session_id) > 12 else obj.session_id
    session_id_short.short_description = 'Session ID'
    session_id_short.admin_order_field = 'session_id'
